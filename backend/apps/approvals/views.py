from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.enums import Role
from apps.common.workspace import WorkspaceScopedMixin

from .models import Approval
from .serializers import ApprovalSerializer, DecisionSerializer
from .services import decide


class ApprovalViewSet(WorkspaceScopedMixin, viewsets.ReadOnlyModelViewSet):
    """Approval Center. Decisions are human-only (JWT users with DEVELOPER+ role)."""

    serializer_class = ApprovalSerializer
    queryset = Approval.objects.select_related("decided_by")
    filterset_fields = ("status", "target_type", "target_id", "research_task", "requested_by_agent")
    action_roles = {"decide": Role.DEVELOPER}

    @extend_schema(request=DecisionSerializer, responses=ApprovalSerializer)
    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        ser = DecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        approval = decide(self.get_object(), user=request.user, membership=request.membership,
                          **ser.validated_data)
        return Response(ApprovalSerializer(approval).data)
