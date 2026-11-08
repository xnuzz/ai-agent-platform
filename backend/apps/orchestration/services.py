"""Agent task lifecycle: create -> claim (lease) -> heartbeat -> results -> complete | fail.

docs/API_CONTRACTS.md §Agent API, docs/WORKFLOWS.md §ResearchTask.
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.enums import TASK_TYPE_AGENT, TaskStatus, TaskType
from apps.common.exceptions import Conflict, InvalidStateTransition

from .ingestion import Ingestor
from .inputs import validate_input
from .models import AgentToken, ResearchTask


def create_task(*, workspace, task_type: str, input_data: dict, actor: Actor, priority: int = 0,
                parent_task=None, software_idea=None) -> ResearchTask:
    clean = validate_input(task_type, input_data, workspace=workspace)
    if task_type == TaskType.SAAS_CUSTOMER_RESEARCH and software_idea is None:
        from apps.research.models import SoftwareIdea

        software_idea = SoftwareIdea.objects.get(pk=clean["software_idea_id"], workspace=workspace)
    task = ResearchTask.objects.create(
        workspace=workspace, agent=TASK_TYPE_AGENT[task_type], task_type=task_type, input=clean,
        priority=priority, created_by=actor.user if actor.is_user else None, parent_task=parent_task,
        software_idea=software_idea,
    )
    record("research_task.created", workspace=workspace, actor=actor, target=task,
           metadata={"task_type": task_type})
    return task


def _release(task: ResearchTask) -> None:
    task.lease_id = None
    task.lease_expires_at = None


def reap_expired_leases(now=None) -> int:
    """RUNNING tasks whose lease expired are re-queued (or failed after max_attempts)."""
    now = now or timezone.now()
    count = 0
    with transaction.atomic():
        for task in (ResearchTask.objects.select_for_update(skip_locked=True)
                     .filter(status=TaskStatus.RUNNING, lease_expires_at__lt=now)):
            if task.cancel_requested:
                task.transition_to(TaskStatus.CANCELLED)
                task.finished_at = now
            elif task.attempt < task.max_attempts:
                task.transition_to(TaskStatus.QUEUED)
            else:
                task.transition_to(TaskStatus.FAILED)
                task.finished_at = now
                task.error = {"code": "lease_expired", "message": "Agent stopped heartbeating.", "retryable": True}
            _release(task)
            task.save()
            record("research_task.lease_expired", workspace=task.workspace, actor=Actor.system(), target=task,
                   metadata={"new_status": task.status, "attempt": task.attempt})
            count += 1
    return count


def claim_task(token: AgentToken, *, worker_id: str, task_types: list[str] | None = None) -> ResearchTask | None:
    reap_expired_leases()
    now = timezone.now()
    with transaction.atomic():
        qs = ResearchTask.objects.select_for_update(skip_locked=True).filter(
            agent=token.agent, status=TaskStatus.QUEUED, cancel_requested=False)
        if task_types:
            qs = qs.filter(task_type__in=task_types)
        task = qs.order_by("-priority", "created_at").first()
        if task is None:
            return None
        task.transition_to(TaskStatus.RUNNING)
        task.attempt += 1
        task.claimed_by = worker_id[:200]
        task.claimed_token = token
        task.lease_id = uuid.uuid4()
        task.lease_expires_at = now + timedelta(seconds=settings.AGENT_TASK_LEASE_SECONDS)
        task.heartbeat_at = now
        task.started_at = task.started_at or now
        task.error = {}
        task.save()
        record("research_task.claimed", workspace=task.workspace, actor=Actor.for_agent_token(token), target=task,
               metadata={"worker_id": task.claimed_by, "attempt": task.attempt})
    return task


def get_owned_task(token: AgentToken, task_id, lease_id, *, lock: bool = True) -> ResearchTask:
    qs = ResearchTask.objects.select_related("workspace", "software_idea")
    if lock:
        qs = qs.select_for_update(of=("self",))
    task = qs.filter(pk=task_id, agent=token.agent).first()
    if task is None:
        raise NotFound("Task not found for this agent.")
    if task.status != TaskStatus.RUNNING:
        raise InvalidStateTransition(f"Task is {task.status}, not RUNNING.", code="task_not_running")
    if not lease_id or str(task.lease_id) != str(lease_id):
        raise Conflict("Lease is not held by this worker (expired or re-claimed).", code="lease_lost")
    return task


@transaction.atomic
def heartbeat(token, task_id, lease_id, *, progress=None, stage=None, message=None) -> ResearchTask:
    task = get_owned_task(token, task_id, lease_id)
    now = timezone.now()
    if progress is not None:
        task.progress = max(0, min(100, int(progress)))
    if stage is not None:
        task.stage = stage[:60]
    if message is not None:
        task.progress_message = message[:500]
    task.heartbeat_at = now
    task.lease_expires_at = now + timedelta(seconds=settings.AGENT_TASK_LEASE_SECONDS)
    task.save(update_fields=["progress", "stage", "progress_message", "heartbeat_at", "lease_expires_at",
                             "updated_at"])
    return task


@transaction.atomic
def submit_results(token, task_id, lease_id, bundle: dict) -> dict:
    task = get_owned_task(token, task_id, lease_id)
    if task.cancel_requested:
        raise Conflict("Task cancellation was requested; results are no longer accepted.", code="cancel_requested")
    actor = Actor.for_agent_token(token)
    report = Ingestor(task, actor).run(bundle)
    record("research_task.results_submitted", workspace=task.workspace, actor=actor, target=task,
           metadata={"created": report["created"], "updated": report["updated"],
                     "approvals": len(report["approvals_requested"])})
    return report


@transaction.atomic
def complete_task(token, task_id, lease_id, *, summary: dict | None = None) -> ResearchTask:
    task = get_owned_task(token, task_id, lease_id)
    task.transition_to(TaskStatus.CANCELLED if task.cancel_requested else TaskStatus.COMPLETED)
    task.result_summary = summary or {}
    task.progress = 100 if task.status == TaskStatus.COMPLETED else task.progress
    task.finished_at = timezone.now()
    _release(task)
    task.save()
    record(f"research_task.{task.status.lower()}", workspace=task.workspace, actor=Actor.for_agent_token(token),
           target=task)
    return task


@transaction.atomic
def fail_task(token, task_id, lease_id, *, code: str, message: str = "", retryable: bool = False) -> ResearchTask:
    task = get_owned_task(token, task_id, lease_id)
    task.error = {"code": code[:60], "message": message[:2000], "retryable": retryable}
    if task.cancel_requested or code == "CANCELLED":
        task.transition_to(TaskStatus.CANCELLED)
        task.finished_at = timezone.now()
    elif retryable and task.attempt < task.max_attempts:
        task.transition_to(TaskStatus.QUEUED)
    else:
        task.transition_to(TaskStatus.FAILED)
        task.finished_at = timezone.now()
    _release(task)
    task.save()
    record("research_task.failed", workspace=task.workspace, actor=Actor.for_agent_token(token), target=task,
           metadata={**task.error, "new_status": task.status})
    return task


@transaction.atomic
def cancel_task(task: ResearchTask, actor: Actor) -> ResearchTask:
    task = ResearchTask.objects.select_for_update().get(pk=task.pk)
    if task.status == TaskStatus.QUEUED:
        task.transition_to(TaskStatus.CANCELLED)
        task.finished_at = timezone.now()
    elif task.status == TaskStatus.RUNNING:
        task.cancel_requested = True  # agent sees it on next heartbeat; lease expiry finalizes it
    else:
        raise InvalidStateTransition(f"Task is already {task.status}.")
    task.save()
    record("research_task.cancel_requested", workspace=task.workspace, actor=actor, target=task)
    return task


@transaction.atomic
def retry_task(task: ResearchTask, actor: Actor) -> ResearchTask:
    task = ResearchTask.objects.select_for_update().get(pk=task.pk)
    task.transition_to(TaskStatus.QUEUED)
    task.attempt, task.error, task.finished_at, task.progress = 0, {}, None, 0
    task.save()
    record("research_task.retried", workspace=task.workspace, actor=actor, target=task)
    return task
