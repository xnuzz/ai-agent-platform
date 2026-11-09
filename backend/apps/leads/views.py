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

from .models import Business, Lead, ProjectBrief
from .serializers import BusinessSerializer, LeadSerializer, LeadStatusSerializer, ProjectBriefSerializer


class BusinessViewSet(WorkspaceScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = BusinessSerializer
    queryset = Business.objects.all()
    filterset_fields = ("city", "country_code", "category", "domain")


class LeadViewSet(WorkspaceScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    serializer_class = LeadSerializer
    queryset = Lead.objects.select_related("business").prefetch_related("evidence")
    filterset_fields = ("status", "source", "software_idea", "research_task", "business")
    ordering_fields = ("created_at", "score")
    http_method_names = ["get", "patch", "post"]

    def perform_update(self, serializer):
        obj = serializer.save()
        record("lead.updated", workspace=obj.workspace, actor=Actor.for_user(self.request.user), target=obj,
               metadata={"fields": sorted(serializer.validated_data)})

    @extend_schema(request=LeadStatusSerializer, responses=LeadSerializer)
    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        ser = LeadStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            lead = self.get_queryset().select_for_update(of=("self",)).get(pk=self.get_object().pk)
            lead.transition_to(ser.validated_data["status"])
            lead.save(update_fields=["status", "updated_at"])
            record("lead.status_changed", workspace=lead.workspace, actor=Actor.for_user(request.user),
                   target=lead, metadata={"status": lead.status})
        return Response(LeadSerializer(lead).data)


class ProjectBriefViewSet(WorkspaceScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = ProjectBriefSerializer
    queryset = ProjectBrief.objects.prefetch_related("evidence")
    filterset_fields = ("status", "lead", "research_task")
    http_method_names = ["get", "patch", "post"]

    def perform_update(self, serializer):
        if not serializer.instance.is_editable:
            raise InvalidStateTransition("Only DRAFT or CHANGES_REQUESTED briefs can be edited.")
        obj = serializer.save()
        record("project_brief.updated", workspace=obj.workspace, actor=Actor.for_user(self.request.user),
               target=obj, metadata={"fields": sorted(serializer.validated_data)})

    @extend_schema(request=SubmitForApprovalSerializer, responses={201: ApprovalSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        ser = SubmitForApprovalSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        approval = request_approval(self.get_object(), actor=Actor.for_user(request.user),
                                    summary=ser.validated_data["summary"])
        return Response(ApprovalSerializer(approval).data, status=201)
