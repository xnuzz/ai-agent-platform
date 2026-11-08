from django.db import models

from apps.common import crypto
from apps.common.enums import IntegrationKind, IntegrationProvider, IntegrationStatus
from apps.common.models import WorkspaceScopedModel


class Integration(WorkspaceScopedModel):
    """A workspace-level connection to an external provider. Secrets are encrypted at rest and write-only."""

    kind = models.CharField(max_length=20, choices=IntegrationKind.choices)
    provider = models.CharField(max_length=30, choices=IntegrationProvider.choices)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=IntegrationStatus.choices, default=IntegrationStatus.ACTIVE)
    config = models.JSONField(default=dict, blank=True)  # NON-secret settings only (host, port, model, ...)
    secret_encrypted = models.TextField(blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")

    def set_secret(self, value: str | None) -> None:
        self.secret_encrypted = crypto.encrypt(value) if value else ""

    def get_secret(self) -> str | None:
        return crypto.decrypt(self.secret_encrypted) if self.secret_encrypted else None

    @property
    def has_secret(self) -> bool:
        return bool(self.secret_encrypted)
