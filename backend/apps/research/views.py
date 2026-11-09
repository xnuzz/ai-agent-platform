from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.approvals.serializers import ApprovalSerializer, SubmitForApprovalSerializer
from apps.approvals.services import request_approval
from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.exceptions import InvalidStateTransition
from apps.common.workspace import WorkspaceScopedMixin

from .models import Evidence, Opportunity, SoftwareIdea
from .serializers import (
    EvidenceSerializer, OpportunitySerializer, OpportunityStatusSerializer, SoftwareIdeaSerializer,
)


class EvidenceViewSet(WorkspaceScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = EvidenceSerializer
    queryset = Evidence.objects.all()
    filterset_fields = ("research_task", "source_type")


class OpportunityViewSet(WorkspaceScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = OpportunitySerializer
    queryset = Opportunity.objects.prefetch_related("evidence")
    filterset_fields = ("research_task", "status", "industry")
    ordering_fields = ("created_at", "score")

    @extend_schema(request=OpportunityStatusSerializer, responses=OpportunitySerializer)
    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        ser = OpportunityStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            opp = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            opp.transition_to(ser.validated_data["status"])
            opp.save(update_fields=["status", "updated_at"])
            record("opportunity.status_changed", workspace=opp.workspace, actor=Actor.for_user(request.user),
                   target=opp, metadata={"status": opp.status})
        return Response(OpportunitySerializer(opp).data)


class SoftwareIdeaViewSet(WorkspaceScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = SoftwareIdeaSerializer
    queryset = SoftwareIdea.objects.prefetch_related("evidence")
    filterset_fields = ("research_task", "status", "opportunity")
    ordering_fields = ("created_at", "score")
    http_method_names = ["get", "patch", "post"]

    def perform_update(self, serializer):
        if not serializer.instance.is_editable:
            raise InvalidStateTransition("Only DRAFT or CHANGES_REQUESTED ideas can be edited.")
        obj = serializer.save()
        record("software_idea.updated", workspace=obj.workspace, actor=Actor.for_user(self.request.user),
               target=obj, metadata={"fields": sorted(serializer.validated_data)})

    @extend_schema(request=SubmitForApprovalSerializer, responses={201: ApprovalSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        ser = SubmitForApprovalSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        approval = request_approval(self.get_object(), actor=Actor.for_user(request.user),
                                    summary=ser.validated_data["summary"])
        return Response(ApprovalSerializer(approval).data, status=201)
