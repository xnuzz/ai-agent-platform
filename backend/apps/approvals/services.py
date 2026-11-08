"""Approval workflow. See docs/WORKFLOWS.md §Approval gates."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.enums import (
    ApprovalDecision, ApprovalStatus, ApprovalTargetType, CampaignStatus, MessageStatus, ReviewStatus, Role,
    TaskType,
)
from apps.common.exceptions import Conflict, InvalidStateTransition
from apps.common.hashing import content_hash
from apps.common.permissions import has_role
from apps.leads.models import ProjectBrief
from apps.outreach.models import Campaign
from apps.research.models import SoftwareIdea

from .models import Approval

TARGET_MODELS = {
    ApprovalTargetType.SOFTWARE_IDEA: SoftwareIdea,
    ApprovalTargetType.PROJECT_BRIEF: ProjectBrief,
    ApprovalTargetType.CAMPAIGN: Campaign,
}
APPROVER_ROLE = Role.DEVELOPER


def target_type_of(obj) -> str:
    for t, model in TARGET_MODELS.items():
        if isinstance(obj, model):
            return t
    raise ValueError(f"{type(obj).__name__} is not approvable.")


def get_target(approval: Approval, *, lock: bool = False):
    qs = TARGET_MODELS[approval.target_type].objects
    if lock:
        qs = qs.select_for_update()
    return qs.get(pk=approval.target_id, workspace_id=approval.workspace_id)


def _evidence(obj) -> list[dict]:
    return [{"id": str(e.id), "url": e.url, "title": e.title, "source_type": e.source_type}
            for e in obj.evidence.all()[:50]]


def build_snapshot(target) -> dict:
    snap = {"content": target.approval_content()}
    if isinstance(target, SoftwareIdea):
        snap["context"] = {
            "opportunity_title": target.opportunity.title if target.opportunity_id else None,
            "evidence": _evidence(target),
        }
    elif isinstance(target, ProjectBrief):
        lead = target.lead
        snap["context"] = {
            "lead_id": str(lead.id), "business_name": lead.business.name, "website": lead.business.website,
            "city": lead.business.city, "lead_score": lead.score, "evidence": _evidence(target),
        }
    elif isinstance(target, Campaign):
        msgs = target.reviewable_messages().select_related("lead__business").order_by("created_at")
        snap["messages"] = [
            {"id": str(m.id), "lead_id": str(m.lead_id), "business_name": m.lead.business.name,
             "to_email": m.to_email, "subject": m.subject, "body": m.body, "hash": m.approved_hash}
            for m in msgs
        ]
        snap["context"] = {"message_count": len(snap["messages"]),
                           "software_idea_id": snap["content"]["software_idea_id"],
                           "project_brief_id": snap["content"]["project_brief_id"]}
    return snap


@transaction.atomic
def request_approval(target, *, actor: Actor, research_task=None, summary: str = "") -> Approval:
    target = type(target).objects.select_for_update().get(pk=target.pk)
    t_type = target_type_of(target)
    if Approval.objects.filter(target_type=t_type, target_id=target.pk, status=ApprovalStatus.PENDING).exists():
        raise Conflict("An approval is already pending for this item.")
    if not target.is_editable:
        raise InvalidStateTransition(f"Cannot submit an item in {target.status} for approval.")

    if isinstance(target, Campaign):
        msgs = list(target.messages.filter(status=MessageStatus.DRAFT))
        if not msgs:
            raise ValidationError({"messages": ["Campaign has no draft messages to approve."]})
        for m in msgs:
            m.transition_to(MessageStatus.WAITING_FOR_APPROVAL)
            m.approved_hash = m.compute_hash()
            m.save(update_fields=["status", "approved_hash", "updated_at"])

    target.transition_to(ReviewStatus.WAITING_FOR_APPROVAL)
    target.save(update_fields=["status", "updated_at"])
    approval = Approval.objects.create(
        workspace=target.workspace, target_type=t_type, target_id=target.pk, research_task=research_task,
        requested_by_type=actor.type, requested_by_user=actor.user if actor.is_user else None,
        requested_by_agent=actor.agent, summary=summary[:5000], snapshot=build_snapshot(target),
        content_hash=content_hash(target.approval_content()),
    )
    record("approval.requested", workspace=target.workspace, actor=actor, target=approval,
           metadata={"target_type": t_type, "target_id": str(target.pk)})
    return approval


@transaction.atomic
def decide(approval: Approval, *, user, membership, decision: str, comment: str = "",
           options: dict | None = None) -> Approval:
    """Apply a human decision. Agents can never reach this function (no agent-facing endpoint)."""
    if not has_role(membership, APPROVER_ROLE):
        raise PermissionDenied("Your role cannot decide approvals.")
    approval = Approval.objects.select_for_update().get(pk=approval.pk)
    if approval.status != ApprovalStatus.PENDING:
        raise InvalidStateTransition(f"Approval is already {approval.status}.")
    target = get_target(approval, lock=True)
    if content_hash(target.approval_content()) != approval.content_hash:
        raise Conflict("Item changed since approval was requested; re-submit it.", code="stale_approval")

    options = options or {}
    actor = Actor.for_user(user)
    outcome: dict = {}
    now = timezone.now()

    if isinstance(target, Campaign):
        _decide_campaign(target, decision)
    else:
        target.transition_to(decision)  # ReviewStatus shares APPROVED/REJECTED/CHANGES_REQUESTED values
        if decision == ApprovalDecision.APPROVED:
            target.approved_at, target.approved_by = now, user
        target.save()

    if decision == ApprovalDecision.APPROVED and isinstance(target, Campaign):
        target.approved_at, target.approved_by = now, user
        target.save(update_fields=["approved_at", "approved_by", "updated_at"])

    if (decision == ApprovalDecision.APPROVED and isinstance(target, SoftwareIdea)
            and options.get("auto_continue", True)):
        from apps.orchestration.services import create_task

        task_input = {"software_idea_id": str(target.pk), **(options.get("customer_research_input") or {})}
        task = create_task(workspace=target.workspace, task_type=TaskType.SAAS_CUSTOMER_RESEARCH,
                           input_data=task_input, actor=actor, parent_task=approval.research_task,
                           software_idea=target)
        outcome["follow_up_task_id"] = str(task.pk)

    approval.status = decision
    approval.decided_by, approval.decided_at = user, now
    approval.decision_comment = comment[:5000]
    approval.decision_options = options
    approval.outcome = outcome
    approval.save()
    record(f"approval.{decision.lower()}", workspace=approval.workspace, actor=actor, target=approval,
           metadata={"target_type": approval.target_type, "target_id": str(approval.target_id), **outcome})
    return approval


def _decide_campaign(campaign: Campaign, decision: str) -> None:
    msgs = list(campaign.messages.select_for_update().filter(status=MessageStatus.WAITING_FOR_APPROVAL))
    if decision == ApprovalDecision.APPROVED:
        stale = [str(m.pk) for m in msgs if m.compute_hash() != m.approved_hash]
        if stale:
            raise Conflict("Messages changed since approval was requested.", details={"message_ids": stale},
                           code="stale_approval")
        if not msgs:
            raise ValidationError({"messages": ["No messages left to approve."]})
    msg_status = {
        ApprovalDecision.APPROVED: MessageStatus.APPROVED,
        ApprovalDecision.REJECTED: MessageStatus.REJECTED,
        ApprovalDecision.CHANGES_REQUESTED: MessageStatus.DRAFT,
    }[decision]
    for m in msgs:
        m.transition_to(msg_status)
        if msg_status == MessageStatus.DRAFT:
            m.approved_hash = ""
        m.save(update_fields=["status", "approved_hash", "updated_at"])
    campaign.transition_to({
        ApprovalDecision.APPROVED: CampaignStatus.APPROVED,
        ApprovalDecision.REJECTED: CampaignStatus.REJECTED,
        ApprovalDecision.CHANGES_REQUESTED: CampaignStatus.CHANGES_REQUESTED,
    }[decision])
    campaign.save(update_fields=["status", "updated_at"])
