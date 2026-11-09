from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.actor import Actor
from apps.common.enums import Role
from apps.common.workspace import WorkspaceScopedMixin

from . import services


class SubjectSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EraseSerializer(SubjectSerializer):
    confirm = serializers.BooleanField(help_text="Must be true. Erasure cannot be undone.")

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError("Set confirm=true to erase.")
        return value


class EraseResultSerializer(serializers.Serializer):
    leads_anonymized = serializers.IntegerField()
    messages_redacted = serializers.IntegerField()
    businesses_updated = serializers.IntegerField()
    suppressed = serializers.BooleanField()


class _PrivacyView(WorkspaceScopedMixin, APIView):
    """ADMIN+ only. Data-subject requests are scoped to the current workspace."""

    write_role = Role.ADMIN

    def get_queryset(self):  # WorkspaceScopedMixin contract; unused
        from apps.leads.models import Lead

        return Lead.objects.none()


class ExportView(_PrivacyView):
    @extend_schema(request=SubjectSerializer, responses=OpenApiResponse(description="All personal data held about "
                   "the email in this workspace (leads, messages, businesses, suppression entries)."), tags=["privacy"])
    def post(self, request):
        ser = SubjectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(services.export_subject(request.workspace, ser.validated_data["email"],
                                                Actor.for_user(request.user)))


class EraseView(_PrivacyView):
    @extend_schema(request=EraseSerializer, responses=EraseResultSerializer, tags=["privacy"])
    def post(self, request):
        ser = EraseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(services.erase_subject(request.workspace, ser.validated_data["email"],
                                               Actor.for_user(request.user)))
