from rest_framework import viewsets

from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.enums import Role
from apps.common.workspace import WorkspaceScopedMixin

from .models import Integration
from .serializers import IntegrationSerializer


class IntegrationViewSet(WorkspaceScopedMixin, viewsets.ModelViewSet):
    serializer_class = IntegrationSerializer
    queryset = Integration.objects.all()
    write_role = Role.ADMIN
    filterset_fields = ("kind", "provider", "status")
    http_method_names = ["get", "post", "patch", "delete"]

    def perform_create(self, serializer):
        obj = serializer.save(workspace=self.request.workspace, created_by=self.request.user)
        record("integration.created", workspace=obj.workspace, actor=Actor.for_user(self.request.user), target=obj,
               metadata={"provider": obj.provider})

    def perform_update(self, serializer):
        obj = serializer.save()
        record("integration.updated", workspace=obj.workspace, actor=Actor.for_user(self.request.user), target=obj,
               metadata={"fields": sorted(k for k in serializer.validated_data if k != "secret"),
                         "secret_changed": "secret" in serializer.validated_data})

    def perform_destroy(self, instance):
        record("integration.deleted", workspace=instance.workspace, actor=Actor.for_user(self.request.user),
               target=instance)
        instance.delete()
