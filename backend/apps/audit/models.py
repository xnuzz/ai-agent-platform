from django.db import models

from apps.common.enums import ActorType
from apps.common.models import UUIDModel


class AuditEvent(UUIDModel):
    """Append-only audit trail. Never updated or deleted through the application."""

    workspace = models.ForeignKey("accounts.Workspace", null=True, on_delete=models.CASCADE, related_name="+")
    actor_type = models.CharField(max_length=10, choices=ActorType.choices)
    actor_user = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="+")
    actor_agent = models.CharField(max_length=40, blank=True)
    action = models.CharField(max_length=80, db_index=True)  # "<entity>.<verb>", e.g. "approval.approved"
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.UUIDField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("AuditEvent is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("AuditEvent is append-only.")
