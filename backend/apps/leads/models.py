from django.db import models

from apps.common.enums import ContactEmailType, LeadStatus, LegalBasis, ReviewStatus, SourceType
from apps.common.models import StatusMachineMixin, WorkspaceScopedModel
from apps.common.normalize import normalize_domain, normalize_name
from apps.research.models import EDITABLE_REVIEW_STATES, REVIEW_TRANSITIONS, SCORE_VALIDATORS


class Business(WorkspaceScopedModel):
    """A real-world organisation. Deduplicated per workspace via dedupe_key."""

    name = models.CharField(max_length=300)
    website = models.URLField(max_length=500, blank=True)
    domain = models.CharField(max_length=255, blank=True, db_index=True)
    email = models.EmailField(blank=True)  # public business address (e.g. info@)
    phone = models.CharField(max_length=50, blank=True)
    address_line1 = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    category = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    source_data = models.JSONField(default=dict, blank=True)  # provider ids (e.g. place_id), raw attributes
    first_seen_task = models.ForeignKey("orchestration.ResearchTask", null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="+")
    dedupe_key = models.CharField(max_length=500)
    evidence = models.ManyToManyField("research.Evidence", blank=True, related_name="businesses")

    class Meta(WorkspaceScopedModel.Meta):
        verbose_name_plural = "businesses"
        constraints = [models.UniqueConstraint(fields=["workspace", "dedupe_key"], name="uniq_business_dedupe")]

    @staticmethod
    def build_dedupe_key(*, name: str, website: str = "", city: str = "", country_code: str = "") -> str:
        domain = normalize_domain(website)
        if domain:
            return f"domain:{domain}"
        return f"name:{normalize_name(name)}|{normalize_name(city)}|{(country_code or '').upper()}"

    def save(self, *args, **kwargs):
        self.domain = normalize_domain(self.website)
        self.country_code = (self.country_code or "").upper()
        if not self.dedupe_key:
            self.dedupe_key = self.build_dedupe_key(
                name=self.name, website=self.website, city=self.city, country_code=self.country_code)
        super().save(*args, **kwargs)


class Lead(WorkspaceScopedModel, StatusMachineMixin):
    """A business qualified as a prospect in a context (local lead or customer of a SoftwareIdea)."""

    STATUS_TRANSITIONS = {
        LeadStatus.NEW: {LeadStatus.QUALIFIED, LeadStatus.DISQUALIFIED, LeadStatus.CONTACTED, LeadStatus.ARCHIVED},
        LeadStatus.QUALIFIED: {LeadStatus.DISQUALIFIED, LeadStatus.CONTACTED, LeadStatus.ARCHIVED},
        LeadStatus.DISQUALIFIED: {LeadStatus.QUALIFIED, LeadStatus.ARCHIVED},
        LeadStatus.CONTACTED: {LeadStatus.REPLIED, LeadStatus.WON, LeadStatus.LOST, LeadStatus.ARCHIVED},
        LeadStatus.REPLIED: {LeadStatus.WON, LeadStatus.LOST, LeadStatus.ARCHIVED},
        LeadStatus.WON: {LeadStatus.ARCHIVED},
        LeadStatus.LOST: {LeadStatus.ARCHIVED},
        LeadStatus.ARCHIVED: set(),
    }
    AGENT_EDITABLE_STATES = {LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.DISQUALIFIED}

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="leads")
    research_task = models.ForeignKey("orchestration.ResearchTask", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="leads")
    source = models.CharField(max_length=20, choices=SourceType.choices)
    software_idea = models.ForeignKey("research.SoftwareIdea", null=True, blank=True, on_delete=models.CASCADE,
                                      related_name="leads")
    status = models.CharField(max_length=20, choices=LeadStatus.choices, default=LeadStatus.NEW, db_index=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True, validators=SCORE_VALIDATORS)
    qualification_notes = models.TextField(blank=True)
    # [{code, title, severity: LOW|MEDIUM|HIGH, description, evidence_ids: [uuid]}] - see AGENT_2_CONTRACT.md
    problems = models.JSONField(default=list, blank=True)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_role = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    contact_email_type = models.CharField(max_length=20, choices=ContactEmailType.choices,
                                          default=ContactEmailType.UNKNOWN)
    legal_basis = models.CharField(max_length=30, choices=LegalBasis.choices, default=LegalBasis.UNKNOWN)
    legal_basis_note = models.TextField(blank=True)  # legitimate-interest assessment summary / consent record
    evidence = models.ManyToManyField("research.Evidence", blank=True, related_name="leads")

    class Meta(WorkspaceScopedModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["workspace", "business", "source", "software_idea"],
                                    name="uniq_lead_context", nulls_distinct=False),
        ]

    @property
    def recipient_email(self) -> str:
        return self.contact_email or self.business.email


class ProjectBrief(WorkspaceScopedModel, StatusMachineMixin):
    """Development proposal for a lead (Agent 2). Requires human approval."""

    AUDIT_TYPE = "PROJECT_BRIEF"
    STATUS_TRANSITIONS = REVIEW_TRANSITIONS

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="project_briefs")
    research_task = models.ForeignKey("orchestration.ResearchTask", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="project_briefs")
    title = models.CharField(max_length=300)
    summary = models.TextField()
    problems = models.JSONField(default=list, blank=True)  # same shape as Lead.problems
    proposed_solution = models.TextField(blank=True)
    scope_items = models.JSONField(default=list, blank=True)  # [str]
    tech_stack = models.JSONField(default=list, blank=True)  # [str]
    estimated_effort_hours_min = models.PositiveIntegerField(null=True, blank=True)
    estimated_effort_hours_max = models.PositiveIntegerField(null=True, blank=True)
    estimated_budget_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    estimated_budget_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    status = models.CharField(max_length=30, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT, db_index=True)
    evidence = models.ManyToManyField("research.Evidence", blank=True, related_name="project_briefs")
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")

    @property
    def is_editable(self) -> bool:
        return self.status in EDITABLE_REVIEW_STATES

    def approval_content(self) -> dict:
        return {
            "lead_id": str(self.lead_id), "title": self.title, "summary": self.summary, "problems": self.problems,
            "proposed_solution": self.proposed_solution, "scope_items": self.scope_items,
            "tech_stack": self.tech_stack,
            "estimated_effort_hours": [self.estimated_effort_hours_min, self.estimated_effort_hours_max],
            "estimated_budget": [str(self.estimated_budget_min) if self.estimated_budget_min is not None else None,
                                 str(self.estimated_budget_max) if self.estimated_budget_max is not None else None],
            "currency": self.currency,
        }
