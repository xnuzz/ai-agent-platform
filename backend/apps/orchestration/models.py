import hashlib
import hmac
import secrets

from django.core.validators import MaxValueValidator
from django.db import models

from apps.common.enums import AgentType, TaskStatus, TaskType
from apps.common.models import StatusMachineMixin, TimeStampedModel, WorkspaceScopedModel


class AgentToken(TimeStampedModel):
    """Service credential for an agent worker. Platform-level (serves all workspaces) and agent-scoped.

    Key format: agt_<prefix>_<secret>. Only the SHA-256 of the full key is stored.
    """

    name = models.CharField(max_length=200)
    agent = models.CharField(max_length=20, choices=AgentType.choices)
    prefix = models.CharField(max_length=16, unique=True)
    key_hash = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def issue(cls, *, name: str, agent: str) -> tuple["AgentToken", str]:
        prefix = secrets.token_hex(6)
        key = f"agt_{prefix}_{secrets.token_urlsafe(32)}"
        return cls.objects.create(name=name, agent=agent, prefix=prefix, key_hash=cls._hash(key)), key

    @classmethod
    def lookup(cls, key: str) -> "AgentToken | None":
        parts = key.split("_", 2)
        if len(parts) != 3 or parts[0] != "agt":
            return None
        token = cls.objects.filter(prefix=parts[1], is_active=True).first()
        if token and hmac.compare_digest(token.key_hash, cls._hash(key)):
            return token
        return None

    def __str__(self):
        return f"{self.name} ({self.agent})"


class ResearchTask(WorkspaceScopedModel, StatusMachineMixin):
    """A unit of agent work. The ResearchTask id IS the background task identifier exposed to all clients."""

    AUDIT_TYPE = "RESEARCH_TASK"
    STATUS_TRANSITIONS = {
        TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
        TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.QUEUED},
        TaskStatus.FAILED: {TaskStatus.QUEUED},  # manual retry
        TaskStatus.COMPLETED: set(),
        TaskStatus.CANCELLED: set(),
    }

    agent = models.CharField(max_length=20, choices=AgentType.choices, db_index=True)
    task_type = models.CharField(max_length=40, choices=TaskType.choices)
    status = models.CharField(max_length=20, choices=TaskStatus.choices, default=TaskStatus.QUEUED, db_index=True)
    input = models.JSONField(default=dict)
    priority = models.SmallIntegerField(default=0)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    parent_task = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="child_tasks")
    software_idea = models.ForeignKey("research.SoftwareIdea", null=True, blank=True, on_delete=models.CASCADE,
                                      related_name="customer_research_tasks")

    # Progress reporting (written by the agent via heartbeat)
    progress = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    stage = models.CharField(max_length=60, blank=True)
    progress_message = models.CharField(max_length=500, blank=True)

    # Lease / execution bookkeeping
    attempt = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    claimed_by = models.CharField(max_length=200, blank=True)  # worker id reported by agent
    claimed_token = models.ForeignKey(AgentToken, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="+")
    lease_id = models.UUIDField(null=True, blank=True)  # rotates on every claim; required on agent writes
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    cancel_requested = models.BooleanField(default=False)

    error = models.JSONField(default=dict, blank=True)  # {code, message, retryable}
    result_summary = models.JSONField(default=dict, blank=True)

    class Meta(WorkspaceScopedModel.Meta):
        indexes = [models.Index(fields=["agent", "status", "-priority", "created_at"], name="task_claim_idx")]


class ResultRef(models.Model):
    """Maps an agent-supplied `ref` (unique within a task + kind) to the created record. Makes result
    submission idempotent and lets later bundles of the same task reference earlier items."""

    task = models.ForeignKey(ResearchTask, on_delete=models.CASCADE, related_name="result_refs")
    kind = models.CharField(max_length=30)
    ref = models.CharField(max_length=200)
    object_id = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "kind", "ref"], name="uniq_result_ref")]
