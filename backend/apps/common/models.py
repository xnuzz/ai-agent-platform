import uuid

from django.db import models

from .exceptions import InvalidStateTransition


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-created_at",)


class WorkspaceScopedModel(TimeStampedModel):
    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE, related_name="+")

    class Meta(TimeStampedModel.Meta):
        abstract = True


class StatusMachineMixin:
    """Enforces documented status transitions (docs/WORKFLOWS.md).

    Subclasses define STATUS_TRANSITIONS = {from_status: {to_status, ...}}.
    """

    STATUS_TRANSITIONS: dict[str, set[str]] = {}

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.STATUS_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status: str) -> None:
        if not self.can_transition_to(new_status):
            raise InvalidStateTransition(
                f"{type(self).__name__} cannot move from {self.status} to {new_status}.",
                details={"from": self.status, "to": new_status},
            )
        self.status = new_status
