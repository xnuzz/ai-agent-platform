from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.enums import EvidenceSourceType, OpportunityStatus, ReviewStatus
from apps.common.models import StatusMachineMixin, WorkspaceScopedModel

SCORE_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]

REVIEW_TRANSITIONS = {
    ReviewStatus.DRAFT: {ReviewStatus.WAITING_FOR_APPROVAL, ReviewStatus.ARCHIVED},
    ReviewStatus.WAITING_FOR_APPROVAL: {ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.CHANGES_REQUESTED},
    ReviewStatus.CHANGES_REQUESTED: {ReviewStatus.WAITING_FOR_APPROVAL, ReviewStatus.ARCHIVED},
    ReviewStatus.APPROVED: {ReviewStatus.ARCHIVED},
    ReviewStatus.REJECTED: {ReviewStatus.ARCHIVED},
    ReviewStatus.ARCHIVED: set(),
}
EDITABLE_REVIEW_STATES = {ReviewStatus.DRAFT, ReviewStatus.CHANGES_REQUESTED}


class Evidence(WorkspaceScopedModel):
    """A source backing a research claim. Every agent finding must cite evidence (source tracking)."""

    research_task = models.ForeignKey("orchestration.ResearchTask", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="evidence")
    url = models.URLField(max_length=2000, blank=True)
    title = models.CharField(max_length=500, blank=True)
    source_type = models.CharField(max_length=20, choices=EvidenceSourceType.choices, default=EvidenceSourceType.OTHER)
    excerpt = models.TextField(blank=True, max_length=5000)
    retrieved_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta(WorkspaceScopedModel.Meta):
        verbose_name_plural = "evidence"


class Opportunity(WorkspaceScopedModel, StatusMachineMixin):
    """A discovered, evidence-backed market problem (Agent 1)."""

    STATUS_TRANSITIONS = {
        OpportunityStatus.NEW: {OpportunityStatus.SHORTLISTED, OpportunityStatus.DISMISSED},
        OpportunityStatus.SHORTLISTED: {OpportunityStatus.DISMISSED, OpportunityStatus.NEW},
        OpportunityStatus.DISMISSED: {OpportunityStatus.NEW},
    }

    research_task = models.ForeignKey("orchestration.ResearchTask", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="opportunities")
    title = models.CharField(max_length=300)
    problem_statement = models.TextField()
    industry = models.CharField(max_length=200, blank=True)
    target_segment = models.CharField(max_length=300, blank=True)
    pain_severity = models.PositiveSmallIntegerField(null=True, blank=True,
                                                     validators=[MinValueValidator(1), MaxValueValidator(5)])
    score = models.PositiveSmallIntegerField(null=True, blank=True, validators=SCORE_VALIDATORS)
    competitors = models.JSONField(default=list, blank=True)  # [{name, url, notes}]
    market_signals = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=OpportunityStatus.choices, default=OpportunityStatus.NEW,
                              db_index=True)
    evidence = models.ManyToManyField(Evidence, blank=True, related_name="opportunities")

    class Meta(WorkspaceScopedModel.Meta):
        verbose_name_plural = "opportunities"


class SoftwareIdea(WorkspaceScopedModel, StatusMachineMixin):
    """A concrete product idea derived from an opportunity. Requires human approval (Agent 1 gate #1)."""

    AUDIT_TYPE = "SOFTWARE_IDEA"
    STATUS_TRANSITIONS = REVIEW_TRANSITIONS

    research_task = models.ForeignKey("orchestration.ResearchTask", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="software_ideas")
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="software_ideas")
    name = models.CharField(max_length=200)
    summary = models.TextField()
    problem = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    target_customers = models.TextField(blank=True)
    key_features = models.JSONField(default=list, blank=True)  # [str]
    pricing_model = models.TextField(blank=True)
    differentiation = models.TextField(blank=True)
    risks = models.JSONField(default=list, blank=True)  # [str]
    mvp_scope = models.TextField(blank=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True, validators=SCORE_VALIDATORS)
    status = models.CharField(max_length=30, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT, db_index=True)
    evidence = models.ManyToManyField(Evidence, blank=True, related_name="software_ideas")
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")

    @property
    def is_editable(self) -> bool:
        return self.status in EDITABLE_REVIEW_STATES

    def approval_content(self) -> dict:
        """Content pinned by an approval (hash must match at decision time)."""
        return {
            "name": self.name, "summary": self.summary, "problem": self.problem, "solution": self.solution,
            "target_customers": self.target_customers, "key_features": self.key_features,
            "pricing_model": self.pricing_model, "differentiation": self.differentiation, "risks": self.risks,
            "mvp_scope": self.mvp_scope, "score": self.score,
            "opportunity_id": str(self.opportunity_id) if self.opportunity_id else None,
        }
