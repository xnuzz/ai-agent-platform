from django.core import signing
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.approvals.serializers import ApprovalSerializer, SubmitForApprovalSerializer
from apps.approvals.services import request_approval
from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.enums import CampaignStatus, MessageStatus, Role, SuppressionSource, SuppressionType
from apps.common.exceptions import InvalidStateTransition
from apps.common.workspace import WorkspaceScopedMixin

from . import services
from .models import Campaign, OutreachMessage, SuppressionEntry
from .serializers import (
    CampaignSerializer, OutreachMessageSerializer, SuppressionEntrySerializer, UnsubscribeInfoSerializer,
)


class CampaignViewSet(WorkspaceScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = CampaignSerializer
    queryset = Campaign.objects.all()
    filterset_fields = ("status", "source", "software_idea", "project_brief", "research_task")
    http_method_names = ["get", "patch", "post"]

    def perform_update(self, serializer):
        if not serializer.instance.is_editable:
            raise InvalidStateTransition("Only DRAFT or CHANGES_REQUESTED campaigns can be edited.")
        obj = serializer.save()
        record("campaign.updated", workspace=obj.workspace, actor=Actor.for_user(self.request.user), target=obj)

    @extend_schema(request=SubmitForApprovalSerializer, responses={201: ApprovalSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        ser = SubmitForApprovalSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        approval = request_approval(self.get_object(), actor=Actor.for_user(request.user),
                                    summary=ser.validated_data["summary"])
        return Response(ApprovalSerializer(approval).data, status=201)

    @extend_schema(request=None, responses=CampaignSerializer)
    @action(detail=True, methods=["post"])
    def launch(self, request, pk=None):
        """APPROVED|PAUSED -> ACTIVE. Backend re-verifies gates and compliance before each send."""
        campaign = services.launch_campaign(self.get_object(), Actor.for_user(request.user))
        return Response(CampaignSerializer(campaign).data)

    @extend_schema(request=None, responses=CampaignSerializer)
    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        c = services.set_campaign_status(self.get_object(), CampaignStatus.PAUSED, Actor.for_user(request.user))
        return Response(CampaignSerializer(c).data)

    @extend_schema(request=None, responses=CampaignSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        c = services.set_campaign_status(self.get_object(), CampaignStatus.CANCELLED, Actor.for_user(request.user))
        return Response(CampaignSerializer(c).data)


class OutreachMessageViewSet(WorkspaceScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                             mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = OutreachMessageSerializer
    queryset = OutreachMessage.objects.select_related("lead__business", "campaign")
    filterset_fields = ("campaign", "lead", "status")
    http_method_names = ["get", "patch", "post"]

    def perform_update(self, serializer):
        msg = serializer.instance
        if msg.status != MessageStatus.DRAFT or not msg.campaign.is_editable:
            raise InvalidStateTransition("Only DRAFT messages in an editable campaign can be edited.")
        obj = serializer.save()
        record("outreach_message.updated", workspace=obj.workspace, actor=Actor.for_user(self.request.user),
               target=obj)

    @extend_schema(request=None, responses=OutreachMessageSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Exclude a message (allowed until it is sent)."""
        msg = self.get_object()
        msg.transition_to(MessageStatus.CANCELLED)
        msg.save(update_fields=["status", "updated_at"])
        record("outreach_message.cancelled", workspace=msg.workspace, actor=Actor.for_user(request.user),
               target=msg)
        return Response(OutreachMessageSerializer(msg).data)


class SuppressionEntryViewSet(WorkspaceScopedMixin, mixins.ListModelMixin, mixins.CreateModelMixin,
                              mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Create: DEVELOPER+. Delete (re-allow contact): ADMIN+ and audited."""

    serializer_class = SuppressionEntrySerializer
    queryset = SuppressionEntry.objects.all()
    filterset_fields = ("type", "reason", "source")
    action_roles = {"destroy": Role.ADMIN}

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        entry = services.add_suppression(
            request.workspace, type_=ser.validated_data["type"], value=ser.validated_data["value"],
            reason=ser.validated_data["reason"], source=SuppressionSource.USER, actor=Actor.for_user(request.user),
            note=ser.validated_data.get("note", ""))
        return Response(SuppressionEntrySerializer(entry).data, status=201)

    def perform_destroy(self, instance):
        record("suppression.deleted", workspace=instance.workspace, actor=Actor.for_user(self.request.user),
               target=instance, metadata={"type": instance.type, "reason": instance.reason})
        instance.delete()


def _mask(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


class UnsubscribeView(APIView):
    """Public opt-out endpoint (no auth). GET = preview, POST = opt out (RFC 8058 one-click compatible)."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public"

    def _data(self, token):
        try:
            return services.read_unsubscribe_token(token)
        except signing.BadSignature:
            raise NotFound("Invalid unsubscribe link.")

    @extend_schema(responses=UnsubscribeInfoSerializer, tags=["public"])
    def get(self, request, token):
        from apps.accounts.models import Workspace

        data = self._data(token)
        ws = Workspace.objects.filter(pk=data["w"]).first()
        if ws is None:
            raise NotFound("Invalid unsubscribe link.")
        already = SuppressionEntry.objects.filter(workspace=ws, type=SuppressionType.EMAIL,
                                                  value=data["e"].lower()).exists()
        return Response({"email_masked": _mask(data["e"]), "sender": ws.sender_company or ws.name,
                         "already_unsubscribed": already})

    @extend_schema(request=None, responses=UnsubscribeInfoSerializer, tags=["public"])
    def post(self, request, token):
        data = self._data(token)
        services.process_unsubscribe(token)
        return Response({"email_masked": _mask(data["e"]), "sender": "", "already_unsubscribed": True})
