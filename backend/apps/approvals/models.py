from django.db import models
from django.db.models import Q

from apps.common.enums import ActorType, ApprovalStatus, ApprovalTargetType
from apps.common.models import WorkspaceScopedModel


class Approval(WorkspaceScopedModel):
    """Human approval gate. The backend - not the agents - enforces that gated actions require APPROVED.

    content_hash pins exactly what the reviewer saw; a decision fails if the target changed.
    """

    AUDIT_TYPE = "APPROVAL"

    target_type = models.CharField(max_length=20, choices=ApprovalTargetType.choices)
    target_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING,
                              db_index=True)
    research_task = models.ForeignKey("orchestration.ResearchTask", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="approvals")
    requested_by_type = models.CharField(max_length=10, choices=ActorType.choices)
    requested_by_user = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name="+")
    requested_by_agent = models.CharField(max_length=40, blank=True)
    summary = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)  # what the reviewer sees (content + display context)
    content_hash = models.CharField(max_length=64)
    decided_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.TextField(blank=True)
    decision_options = models.JSONField(default=dict, blank=True)
    outcome = models.JSONField(default=dict, blank=True)  # side effects, e.g. {"follow_up_task_id": ...}

    class Meta(WorkspaceScopedModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["target_type", "target_id"], condition=Q(status="PENDING"),
                                    name="uniq_pending_approval_per_target"),
        ]
