from django.db.models import Count
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.approvals.models import Approval
from apps.common.enums import ApprovalStatus, TaskStatus
from apps.common.workspace import WorkspaceScopedMixin
from apps.leads.models import Lead, ProjectBrief
from apps.orchestration.models import ResearchTask
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
