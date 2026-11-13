from datetime import timedelta

from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.approvals.models import Approval
from apps.common.enums import AgentType, ApprovalStatus, LeadStatus, MessageStatus, TaskStatus
from apps.common.workspace import WorkspaceScopedMixin
from apps.leads.models import Business, Lead, ProjectBrief
from apps.orchestration.models import AgentToken, ResearchTask
from apps.outreach.models import Campaign, OutreachMessage
from apps.research.models import Opportunity, SoftwareIdea


def _by_status(qs, field="status") -> dict:
    return {row[field]: row["n"] for row in qs.values(field).annotate(n=Count("id")).order_by()}


class DashboardSummaryView(WorkspaceScopedMixin, APIView):
    def get_queryset(self):  # WorkspaceScopedMixin contract; unused
        return ResearchTask.objects.none()

    @extend_schema(responses=OpenApiResponse(description="Counts by status per entity for the workspace."))
    def get(self, request):
        ws = request.workspace
        active = [TaskStatus.QUEUED, TaskStatus.RUNNING]
        return Response({
            "research_tasks": _by_status(ResearchTask.objects.filter(workspace=ws)),
            "active_tasks_by_agent": _by_status(ResearchTask.objects.filter(workspace=ws, status__in=active),
                                                "agent"),
            "pending_approvals": _by_status(
                Approval.objects.filter(workspace=ws, status=ApprovalStatus.PENDING), "target_type"),
            "opportunities": _by_status(Opportunity.objects.filter(workspace=ws)),
            "software_ideas": _by_status(SoftwareIdea.objects.filter(workspace=ws)),
            "leads": _by_status(Lead.objects.filter(workspace=ws)),
            "leads_by_source": _by_status(Lead.objects.filter(workspace=ws), "source"),
            "project_briefs": _by_status(ProjectBrief.objects.filter(workspace=ws)),
            "campaigns": _by_status(Campaign.objects.filter(workspace=ws)),
            "outreach_messages": _by_status(OutreachMessage.objects.filter(workspace=ws)),
        })


# ---------------------------------------------------------------- operations

STUCK_SENDING_AFTER = timedelta(minutes=15)   # a send that has not finished by now needs a human decision
WORKER_OFFLINE_AFTER = timedelta(minutes=10)  # agent tokens record use at most once a minute
QUEUE_WAIT_ALERT = timedelta(minutes=10)


class CurrentTaskSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    task_type = serializers.CharField()
    stage = serializers.CharField()
    progress = serializers.IntegerField()
    progress_message = serializers.CharField()
    attempt = serializers.IntegerField()
    heartbeat_at = serializers.DateTimeField(allow_null=True)
    lease_expires_at = serializers.DateTimeField(allow_null=True)


class TaskErrorSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    status = serializers.CharField()
    code = serializers.CharField()
    message = serializers.CharField()
    at = serializers.DateTimeField()


class AgentOpsSerializer(serializers.Serializer):
    agent = serializers.CharField()
    state = serializers.ChoiceField(choices=["RUNNING", "IDLE", "WAITING", "STALLED", "OFFLINE"])
    worker_last_seen_at = serializers.DateTimeField(allow_null=True)
    last_heartbeat_at = serializers.DateTimeField(allow_null=True)
    last_success_at = serializers.DateTimeField(allow_null=True)
    current_tasks = CurrentTaskSerializer(many=True)
    queued = serializers.IntegerField()
    oldest_queued_at = serializers.DateTimeField(allow_null=True)
    stuck = serializers.IntegerField(help_text="RUNNING tasks whose lease expired (the reaper requeues or fails them)")
    failed_24h = serializers.IntegerField()
    retries_24h = serializers.IntegerField(help_text="Extra attempts on tasks updated in the last 24 h")
    recent_errors = TaskErrorSerializer(many=True)
    businesses = serializers.IntegerField()
    leads = serializers.IntegerField()
    qualified_leads = serializers.IntegerField()


class AlertSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=["warning", "critical"])
    code = serializers.CharField()
    message = serializers.CharField()
    agent = serializers.CharField(allow_blank=True)


class OperationsSerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    agents = AgentOpsSerializer(many=True)
    messages_stuck_sending = serializers.IntegerField()
    alerts = AlertSerializer(many=True)


def _agent_ops(ws, agent: str, now) -> tuple[dict, list[dict]]:
    tasks = ResearchTask.objects.filter(workspace=ws, agent=agent)
    day = now - timedelta(days=1)
    running = list(tasks.filter(status=TaskStatus.RUNNING).order_by("started_at"))
    queued = tasks.filter(status=TaskStatus.QUEUED)
    agg = tasks.aggregate(
        last_hb=Max("heartbeat_at"), last_ok=Max("finished_at", filter=Q(status=TaskStatus.COMPLETED)),
        failed=Count("id", filter=Q(status=TaskStatus.FAILED, updated_at__gte=day)),
        attempts=Sum("attempt", filter=Q(updated_at__gte=day, attempt__gt=1)),
        retried=Count("id", filter=Q(updated_at__gte=day, attempt__gt=1)),
    )
    oldest_q = queued.order_by("created_at").values_list("created_at", flat=True).first()
    stuck = [t for t in running if t.lease_expires_at and t.lease_expires_at < now]
    seen = AgentToken.objects.filter(agent=agent, revoked_at__isnull=True).aggregate(m=Max("last_used_at"))["m"]
    online = bool(seen and now - seen <= WORKER_OFFLINE_AFTER)
    state = ("STALLED" if stuck else "RUNNING" if running else "OFFLINE" if not online
             else "WAITING" if oldest_q else "IDLE")
    errors = [{"task_id": t.id, "status": t.status, "code": str(t.error.get("code", "")),
               "message": str(t.error.get("message", ""))[:300], "at": t.updated_at}
              for t in tasks.filter(updated_at__gte=day).exclude(error={}).order_by("-updated_at")[:5]]
    leads = Lead.objects.filter(workspace=ws, source=agent)
    data = {
        "agent": agent, "state": state, "worker_last_seen_at": seen, "last_heartbeat_at": agg["last_hb"],
        "last_success_at": agg["last_ok"], "queued": queued.count(), "oldest_queued_at": oldest_q,
        "current_tasks": [{"id": t.id, "task_type": t.task_type, "stage": t.stage, "progress": t.progress,
                           "progress_message": t.progress_message, "attempt": t.attempt,
                           "heartbeat_at": t.heartbeat_at, "lease_expires_at": t.lease_expires_at}
                          for t in running],
        "stuck": len(stuck), "failed_24h": agg["failed"],
        "retries_24h": (agg["attempts"] or 0) - (agg["retried"] or 0),
        "recent_errors": errors,
        "businesses": Business.objects.filter(workspace=ws, leads__source=agent).distinct().count(),
        "leads": leads.count(),
        "qualified_leads": leads.filter(status__in=[LeadStatus.QUALIFIED, LeadStatus.CONTACTED,
                                                    LeadStatus.REPLIED, LeadStatus.WON]).count(),
    }
    label, alerts = AgentType(agent).label, []
    if stuck:
        alerts.append({"level": "critical", "code": "task_stalled", "agent": agent,
                       "message": f"{label}: {len(stuck)} running task(s) stopped heartbeating; the lease reaper "
                                  f"requeues or fails them within a minute."})
    if oldest_q and not online and now - oldest_q > QUEUE_WAIT_ALERT:
        alerts.append({"level": "critical", "code": "worker_offline", "agent": agent,
                       "message": f"{label}: a task has been queued since {oldest_q:%Y-%m-%d %H:%M} UTC and no "
                                  f"worker has called the API for over 10 min."})
    if agg["failed"]:
        alerts.append({"level": "warning", "code": "tasks_failed", "agent": agent,
                       "message": f"{label}: {agg['failed']} task(s) failed in the last 24 h."})
    return data, alerts


class OperationsView(WorkspaceScopedMixin, APIView):
    """Agent health for this workspace, computed from tasks, leases, heartbeats and agent-token use."""

    def get_queryset(self):  # WorkspaceScopedMixin contract; unused
        return ResearchTask.objects.none()

    @extend_schema(responses=OperationsSerializer)
    def get(self, request):
        ws, now = request.workspace, timezone.now()
        agents, alerts = [], []
        for agent in AgentType.values:
            data, a = _agent_ops(ws, agent, now)
            agents.append(data)
            alerts += a
        stuck_sending = OutreachMessage.objects.filter(workspace=ws, status=MessageStatus.SENDING,
                                                       updated_at__lt=now - STUCK_SENDING_AFTER).count()
        if stuck_sending:
            alerts.append({"level": "critical", "code": "messages_stuck_sending", "agent": "",
                           "message": f"{stuck_sending} message(s) stuck in SENDING for over 15 min: check the mail "
                                      f"provider log, then resolve each as SENT or FAILED (never resent automatically)."})
        alerts.sort(key=lambda x: x["level"] != "critical")
        return Response(OperationsSerializer({"generated_at": now, "agents": agents,
                                              "messages_stuck_sending": stuck_sending, "alerts": alerts}).data)
