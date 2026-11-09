from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.views import MembershipViewSet, MeView, RegisterView, WorkspaceViewSet
from apps.approvals.views import ApprovalViewSet
from apps.audit.views import AuditEventViewSet
from apps.dashboard.views import DashboardSummaryView
from apps.integrations.views import IntegrationViewSet
from apps.leads.views import BusinessViewSet, LeadViewSet, ProjectBriefViewSet
from apps.orchestration import views as orch
from apps.outreach.views import CampaignViewSet, OutreachMessageViewSet, SuppressionEntryViewSet, UnsubscribeView
from apps.privacy.views import EraseView, ExportView
from apps.research.views import EvidenceViewSet, OpportunityViewSet, SoftwareIdeaViewSet


def healthz(request):
    return JsonResponse({"status": "ok"})


router = DefaultRouter()
router.register("workspaces", WorkspaceViewSet, basename="workspace")
router.register("members", MembershipViewSet, basename="member")
router.register("research-tasks", orch.ResearchTaskViewSet, basename="research-task")
router.register("evidence", EvidenceViewSet, basename="evidence")
router.register("opportunities", OpportunityViewSet, basename="opportunity")
router.register("software-ideas", SoftwareIdeaViewSet, basename="software-idea")
router.register("businesses", BusinessViewSet, basename="business")
router.register("leads", LeadViewSet, basename="lead")
router.register("project-briefs", ProjectBriefViewSet, basename="project-brief")
router.register("campaigns", CampaignViewSet, basename="campaign")
router.register("outreach-messages", OutreachMessageViewSet, basename="outreach-message")
router.register("approvals", ApprovalViewSet, basename="approval")
router.register("suppression-entries", SuppressionEntryViewSet, basename="suppression-entry")
router.register("integrations", IntegrationViewSet, basename="integration")
router.register("audit-events", AuditEventViewSet, basename="audit-event")

agent_patterns = [
    path("tasks/claim/", orch.AgentClaimView.as_view(), name="agent-claim"),
    path("tasks/<uuid:task_id>/", orch.AgentTaskDetailView.as_view(), name="agent-task"),
    path("tasks/<uuid:task_id>/heartbeat/", orch.AgentHeartbeatView.as_view(), name="agent-heartbeat"),
    path("tasks/<uuid:task_id>/results/", orch.AgentResultsView.as_view(), name="agent-results"),
    path("tasks/<uuid:task_id>/complete/", orch.AgentCompleteView.as_view(), name="agent-complete"),
    path("tasks/<uuid:task_id>/fail/", orch.AgentFailView.as_view(), name="agent-fail"),
    path("suppression/check/", orch.AgentSuppressionCheckView.as_view(), name="agent-suppression-check"),
]

api_v1 = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="auth-token"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("privacy/export/", ExportView.as_view(), name="privacy-export"),
    path("privacy/erase/", EraseView.as_view(), name="privacy-erase"),
    path("public/unsubscribe/<str:token>/", UnsubscribeView.as_view(), name="public-unsubscribe"),
    path("agent/", include(agent_patterns)),
    path("", include(router.urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("healthz", healthz, name="healthz"),
]
