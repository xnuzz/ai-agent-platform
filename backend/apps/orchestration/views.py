from django.db.models import Prefetch  # noqa: F401
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.actor import Actor
from apps.common.workspace import WorkspaceScopedMixin

from . import services
from .authentication import AgentTokenAuthentication
from .bundle import ResultBundle
from .models import AgentToken, ResearchTask
from .serializers import (
    AgentTaskSerializer, ClaimRequestSerializer, ClaimResponseSerializer, CompleteRequestSerializer,
    FailRequestSerializer, HeartbeatRequestSerializer, HeartbeatResponseSerializer, ResearchTaskCreateSerializer,
    ResearchTaskDetailSerializer, ResearchTaskSerializer, ResultReportSerializer, SuppressionCheckSerializer,
)

LEASE_HEADER = OpenApiParameter("X-Lease-Id", str, OpenApiParameter.HEADER, required=True,
                                description="lease_id returned by claim")


# ---------------------------------------------------------------- user-facing

class ResearchTaskViewSet(WorkspaceScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = ResearchTask.objects.all()
    filterset_fields = ("status", "agent", "task_type", "software_idea", "parent_task")
    ordering_fields = ("created_at", "priority")

    def get_serializer_class(self):
        if self.action == "create":
            return ResearchTaskCreateSerializer
        return ResearchTaskDetailSerializer if self.action == "retrieve" else ResearchTaskSerializer

    @extend_schema(request=ResearchTaskCreateSerializer, responses={201: ResearchTaskSerializer})
    def create(self, request, *args, **kwargs):
        ser = ResearchTaskCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = services.create_task(workspace=request.workspace, task_type=ser.validated_data["task_type"],
                                    input_data=ser.validated_data["input"], priority=ser.validated_data["priority"],
                                    actor=Actor.for_user(request.user))
        return Response(ResearchTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=ResearchTaskSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        task = services.cancel_task(self.get_object(), Actor.for_user(request.user))
        return Response(ResearchTaskSerializer(task).data)

    @extend_schema(request=None, responses=ResearchTaskSerializer)
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        task = services.retry_task(self.get_object(), Actor.for_user(request.user))
        return Response(ResearchTaskSerializer(task).data)


# ---------------------------------------------------------------- agent-facing

class IsAgent(BasePermission):
    def has_permission(self, request, view):
        return isinstance(getattr(request, "auth", None), AgentToken)


class AgentAPIView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [IsAgent]

    @property
    def token(self) -> AgentToken:
        return self.request.auth

    def lease(self):
        return self.request.headers.get("X-Lease-Id", "")


class AgentClaimView(AgentAPIView):
    @extend_schema(request=ClaimRequestSerializer, responses=ClaimResponseSerializer, tags=["agent"])
    def post(self, request):
        ser = ClaimRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = services.claim_task(self.token, worker_id=ser.validated_data["worker_id"],
                                   task_types=ser.validated_data.get("task_types"))
        return Response({"task": AgentTaskSerializer(task).data if task else None})


class AgentTaskDetailView(AgentAPIView):
    @extend_schema(responses=AgentTaskSerializer, tags=["agent"])
    def get(self, request, task_id):
        task = ResearchTask.objects.filter(pk=task_id, agent=self.token.agent).first()
        if task is None:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        return Response(AgentTaskSerializer(task).data)


class AgentHeartbeatView(AgentAPIView):
    @extend_schema(request=HeartbeatRequestSerializer, responses=HeartbeatResponseSerializer,
                   parameters=[LEASE_HEADER], tags=["agent"])
    def post(self, request, task_id):
        ser = HeartbeatRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = services.heartbeat(self.token, task_id, self.lease(), **ser.validated_data)
        return Response({"status": task.status, "cancel_requested": task.cancel_requested,
                         "lease_expires_at": task.lease_expires_at})


class AgentResultsView(AgentAPIView):
    @extend_schema(request=ResultBundle, responses=ResultReportSerializer, parameters=[LEASE_HEADER],
                   tags=["agent"])
    def post(self, request, task_id):
        ser = ResultBundle(data=request.data)
        ser.is_valid(raise_exception=True)
        report = services.submit_results(self.token, task_id, self.lease(), ser.validated_data)
        return Response(report)


class AgentCompleteView(AgentAPIView):
    @extend_schema(request=CompleteRequestSerializer, responses=AgentTaskSerializer, parameters=[LEASE_HEADER],
                   tags=["agent"])
    def post(self, request, task_id):
        ser = CompleteRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = services.complete_task(self.token, task_id, self.lease(), summary=ser.validated_data["summary"])
        return Response(AgentTaskSerializer(task).data)


class AgentFailView(AgentAPIView):
    @extend_schema(request=FailRequestSerializer, responses=AgentTaskSerializer, parameters=[LEASE_HEADER],
                   tags=["agent"])
    def post(self, request, task_id):
        ser = FailRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = services.fail_task(self.token, task_id, self.lease(), **ser.validated_data)
        return Response(AgentTaskSerializer(task).data)


class AgentSuppressionCheckView(AgentAPIView):
    @extend_schema(request=SuppressionCheckSerializer,
                   responses=OpenApiResponse(description='{"suppressed_emails": [...], "suppressed_phones": [...]}'),
                   tags=["agent"])
    def post(self, request):
        from apps.outreach.services import is_suppressed

        ser = SuppressionCheckSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = ResearchTask.objects.filter(pk=ser.validated_data["task_id"], agent=self.token.agent).first()
        if task is None:
            raise PermissionDenied("Unknown task for this agent.")
        ws = task.workspace_id
        return Response({
            "suppressed_emails": [e for e in ser.validated_data["emails"] if is_suppressed(ws, email=e)],
            "suppressed_phones": [p for p in ser.validated_data["phones"] if is_suppressed(ws, phone=p)],
        })
