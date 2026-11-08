from django.db import models

from apps.common.enums import (
    CampaignStatus, Channel, MessageStatus, SourceType, SuppressionReason, SuppressionSource, SuppressionType,
)
from apps.common.hashing import content_hash
from apps.common.models import StatusMachineMixin, WorkspaceScopedModel

EDITABLE_CAMPAIGN_STATES = {CampaignStatus.DRAFT, CampaignStatus.CHANGES_REQUESTED}


class Campaign(WorkspaceScopedModel, StatusMachineMixin):
    """A set of outreach messages approved and executed together. Requires human approval."""

    AUDIT_TYPE = "CAMPAIGN"
    STATUS_TRANSITIONS = {
        CampaignStatus.DRAFT: {CampaignStatus.WAITING_FOR_APPROVAL, CampaignStatus.CANCELLED},
        CampaignStatus.CHANGES_REQUESTED: {CampaignStatus.WAITING_FOR_APPROVAL, CampaignStatus.CANCELLED},
        CampaignStatus.WAITING_FOR_APPROVAL: {
            CampaignStatus.APPROVED, CampaignStatus.REJECTED, CampaignStatus.CHANGES_REQUESTED,
        },
        CampaignStatus.APPROVED: {CampaignStatus.ACTIVE, CampaignStatus.CANCELLED},
        CampaignStatus.ACTIVE: {CampaignStatus.PAUSED, CampaignStatus.COMPLETED, CampaignStatus.CANCELLED},
        CampaignStatus.PAUSED: {CampaignStatus.ACTIVE, CampaignStatus.CANCELLED},
        CampaignStatus.REJECTED: set(),
        CampaignStatus.COMPLETED: set(),
        CampaignStatus.CANCELLED: set(),
    }

    name = models.CharField(max_length=300)
    source = models.CharField(max_length=20, choices=SourceType.choices)
    research_task = models.ForeignKey("orchestration.ResearchTask", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="campaigns")
    software_idea = models.ForeignKey("research.SoftwareIdea", null=True, blank=True, on_delete=models.PROTECT,
                                      related_name="campaigns")
    project_brief = models.ForeignKey("leads.ProjectBrief", null=True, blank=True, on_delete=models.PROTECT,
                                      related_name="campaigns")
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    offer = models.JSONField(default=dict, blank=True)  # {headline, value_proposition, pricing, call_to_action}
    status = models.CharField(max_length=30, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT,
                              db_index=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    launched_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_editable(self) -> bool:
        return self.status in EDITABLE_CAMPAIGN_STATES

    def reviewable_messages(self):
        return self.messages.exclude(status__in=[MessageStatus.CANCELLED, MessageStatus.SUPPRESSED])

    def approval_content(self) -> dict:
        """Campaign-level content. Messages are pinned individually via OutreachMessage.approved_hash."""
        return {
            "name": self.name, "channel": self.channel, "offer": self.offer,
            "software_idea_id": str(self.software_idea_id) if self.software_idea_id else None,
            "project_brief_id": str(self.project_brief_id) if self.project_brief_id else None,
        }


class OutreachMessage(WorkspaceScopedModel, StatusMachineMixin):
    STATUS_TRANSITIONS = {
        MessageStatus.DRAFT: {MessageStatus.WAITING_FOR_APPROVAL, MessageStatus.CANCELLED, MessageStatus.SUPPRESSED},
        MessageStatus.WAITING_FOR_APPROVAL: {
            MessageStatus.APPROVED, MessageStatus.REJECTED, MessageStatus.DRAFT, MessageStatus.CANCELLED,
            MessageStatus.SUPPRESSED,
        },
        MessageStatus.APPROVED: {MessageStatus.SENDING, MessageStatus.SUPPRESSED, MessageStatus.CANCELLED,
                                 MessageStatus.FAILED},
        MessageStatus.SENDING: {MessageStatus.SENT, MessageStatus.FAILED},
        MessageStatus.REJECTED: set(),
        MessageStatus.SENT: set(),
        MessageStatus.FAILED: set(),
        MessageStatus.SUPPRESSED: set(),
        MessageStatus.CANCELLED: set(),
    }

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="messages")
    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="outreach_messages")
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    sequence_step = models.PositiveSmallIntegerField(default=1)  # v1: only step 1 exists
    to_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=300, blank=True)
    body = models.TextField()  # plain text; backend appends sender identity + unsubscribe footer
    language = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=30, choices=MessageStatus.choices, default=MessageStatus.DRAFT,
                              db_index=True)
    approved_hash = models.CharField(max_length=64, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=300, blank=True)
    error = models.JSONField(default=dict, blank=True)

    class Meta(WorkspaceScopedModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["campaign", "lead", "sequence_step"], name="uniq_campaign_lead_step"),
        ]

    def approval_content(self) -> dict:
        return {"lead_id": str(self.lead_id), "to_email": self.to_email, "subject": self.subject,
                "body": self.body, "channel": self.channel, "sequence_step": self.sequence_step}

    def compute_hash(self) -> str:
        return content_hash(self.approval_content())


class SuppressionEntry(WorkspaceScopedModel):
    """Do-not-contact list. Checked at draft ingestion AND immediately before every send."""

    type = models.CharField(max_length=10, choices=SuppressionType.choices)
    value = models.CharField(max_length=320)  # normalized: lower-case email / bare domain / E.164-ish phone
    reason = models.CharField(max_length=20, choices=SuppressionReason.choices)
    source = models.CharField(max_length=20, choices=SuppressionSource.choices, default=SuppressionSource.USER)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")

    class Meta(WorkspaceScopedModel.Meta):
        verbose_name_plural = "suppression entries"
        constraints = [models.UniqueConstraint(fields=["workspace", "type", "value"], name="uniq_suppression")]
