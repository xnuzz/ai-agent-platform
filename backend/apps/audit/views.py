from rest_framework import viewsets

from apps.common.enums import Role
from apps.common.workspace import WorkspaceScopedMixin

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(WorkspaceScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditEventSerializer
    queryset = AuditEvent.objects.select_related("actor_user")
    filterset_fields = ("action", "actor_type", "target_type", "target_id")
    action_roles = {"list": Role.ADMIN, "retrieve": Role.ADMIN}
