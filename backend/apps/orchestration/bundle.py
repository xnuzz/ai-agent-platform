"""Result bundle schema v1.0 — the ONLY way agents persist research output.

Contract: docs/API_CONTRACTS.md §Agent result bundle. Every item carries an agent-chosen `ref`
(unique per task + kind); re-submitting the same ref is idempotent.
"""
from django.conf import settings
from rest_framework import serializers

from apps.common.enums import Channel, ContactEmailType, EvidenceSourceType, LeadStatus, LegalBasis

SCHEMA_VERSION = "1.0"
Ref = lambda **kw: serializers.CharField(max_length=200, **kw)  # noqa: E731
RefList = lambda: serializers.ListField(child=Ref(), required=False, default=list, max_length=100)  # noqa: E731
Score = lambda: serializers.IntegerField(min_value=0, max_value=100, required=False, allow_null=True)  # noqa: E731
Text = lambda n=None: serializers.CharField(required=False, allow_blank=True, default="",  # noqa: E731
                                            **({"max_length": n} if n else {}))
StrList = lambda: serializers.ListField(child=serializers.CharField(max_length=500), required=False,  # noqa: E731
                                        default=list, max_length=50)


class EvidenceItem(serializers.Serializer):
    ref = Ref()
    url = serializers.URLField(max_length=2000, required=False, allow_blank=True, default="")
    title = Text(500)
    source_type = serializers.ChoiceField(choices=EvidenceSourceType.choices, default=EvidenceSourceType.OTHER)
    excerpt = Text(5000)
    retrieved_at = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.DictField(required=False, default=dict)


class CompetitorItem(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    url = serializers.URLField(max_length=500, required=False, allow_blank=True, default="")
    notes = Text(2000)


class OpportunityItem(serializers.Serializer):
    ref = Ref()
    title = serializers.CharField(max_length=300)
    problem_statement = serializers.CharField()
    industry = Text(200)
    target_segment = Text(300)
    pain_severity = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    score = Score()
    competitors = CompetitorItem(many=True, required=False, default=list)
    market_signals = serializers.DictField(required=False, default=dict)
    evidence_refs = RefList()


class ApprovalFlags(serializers.Serializer):
    submit_for_approval = serializers.BooleanField(default=False)
    approval_summary = Text(5000)


class SoftwareIdeaItem(ApprovalFlags):
    ref = Ref()
    opportunity_ref = Ref(required=False, allow_null=True)
    name = serializers.CharField(max_length=200)
    summary = serializers.CharField()
    problem = Text()
    solution = Text()
    target_customers = Text()
    key_features = StrList()
    pricing_model = Text()
    differentiation = Text()
    risks = StrList()
    mvp_scope = Text()
    score = Score()
    evidence_refs = RefList()


class AddressItem(serializers.Serializer):
    line1 = Text(300)
    city = Text(120)
    region = Text(120)
    postal_code = Text(20)
    country_code = serializers.CharField(max_length=2, required=False, allow_blank=True, default="")


class BusinessItem(serializers.Serializer):
    ref = Ref()
    name = serializers.CharField(max_length=300)
    website = serializers.URLField(max_length=500, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = Text(50)
    address = AddressItem(required=False, default=dict)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    category = Text(200)
    description = Text()
    source_data = serializers.DictField(required=False, default=dict)
    evidence_refs = RefList()


class ProblemItem(serializers.Serializer):
    code = serializers.RegexField(r"^[A-Z][A-Z0-9_]{1,59}$")
    title = serializers.CharField(max_length=300)
    severity = serializers.ChoiceField(choices=["LOW", "MEDIUM", "HIGH"], default="MEDIUM")
    description = Text(5000)
    evidence_refs = RefList()


class ContactItem(serializers.Serializer):
    name = Text(200)
    role = Text(200)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = Text(50)
    email_type = serializers.ChoiceField(choices=ContactEmailType.choices, default=ContactEmailType.UNKNOWN)
    legal_basis = serializers.ChoiceField(choices=LegalBasis.choices, default=LegalBasis.UNKNOWN)
    legal_basis_note = Text(2000)


class LeadItem(serializers.Serializer):
    ref = Ref()
    business_ref = Ref(required=False, allow_null=True)
    business_id = serializers.UUIDField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=[LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.DISQUALIFIED],
                                     default=LeadStatus.NEW)
    score = Score()
    qualification_notes = Text()
    problems = ProblemItem(many=True, required=False, default=list)
    contact = ContactItem(required=False, default=dict)
    evidence_refs = RefList()

    def validate(self, attrs):
        if bool(attrs.get("business_ref")) == bool(attrs.get("business_id")):
            raise serializers.ValidationError("Provide exactly one of business_ref or business_id.")
        return attrs


class RangeItem(serializers.Serializer):
    min = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True)
    max = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")


class ProjectBriefItem(ApprovalFlags):
    ref = Ref()
    lead_ref = Ref(required=False, allow_null=True)
    lead_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=300)
    summary = serializers.CharField()
    problems = ProblemItem(many=True, required=False, default=list)
    proposed_solution = Text()
    scope_items = StrList()
    tech_stack = StrList()
    estimated_effort_hours = RangeItem(required=False, default=dict)
    estimated_budget = RangeItem(required=False, default=dict)
    evidence_refs = RefList()

    def validate(self, attrs):
        if bool(attrs.get("lead_ref")) == bool(attrs.get("lead_id")):
            raise serializers.ValidationError("Provide exactly one of lead_ref or lead_id.")
        return attrs


class MessageItem(serializers.Serializer):
    lead_ref = Ref(required=False, allow_null=True)
    lead_id = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.CharField(max_length=300)
    body = serializers.CharField(max_length=20000)
    language = Text(10)
    sequence_step = serializers.IntegerField(min_value=1, max_value=1, default=1)  # follow-ups: v2

    def validate(self, attrs):
        if bool(attrs.get("lead_ref")) == bool(attrs.get("lead_id")):
            raise serializers.ValidationError("Provide exactly one of lead_ref or lead_id.")
        return attrs


class OfferItem(serializers.Serializer):
    headline = Text(300)
    value_proposition = Text(5000)
    pricing = Text(2000)
    call_to_action = Text(500)


class CampaignItem(ApprovalFlags):
    ref = Ref()
    name = serializers.CharField(max_length=300)
    channel = serializers.ChoiceField(choices=Channel.choices, default=Channel.EMAIL)
    offer = OfferItem(required=False, default=dict)
    project_brief_ref = Ref(required=False, allow_null=True)
    project_brief_id = serializers.UUIDField(required=False, allow_null=True)
    messages = MessageItem(many=True, required=False, default=list)


def _section(item_cls):
    return item_cls(many=True, required=False, default=list,
                    max_length=settings.AGENT_RESULT_MAX_ITEMS_PER_SECTION)


class ResultBundle(serializers.Serializer):
    schema_version = serializers.ChoiceField(choices=[SCHEMA_VERSION])
    evidence = _section(EvidenceItem)
    opportunities = _section(OpportunityItem)
    software_ideas = _section(SoftwareIdeaItem)
    businesses = _section(BusinessItem)
    leads = _section(LeadItem)
    project_briefs = _section(ProjectBriefItem)
    campaigns = _section(CampaignItem)
