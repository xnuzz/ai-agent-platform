"""Input schemas per task type (docs/AGENT_1_CONTRACT.md, docs/AGENT_2_CONTRACT.md)."""
import uuid

from rest_framework import serializers

from apps.common.enums import Channel, ReviewStatus, TaskType

LANG = dict(max_length=10, default="en")


class CountryCodeField(serializers.CharField):
    def __init__(self, **kw):
        super().__init__(min_length=2, max_length=2, **kw)

    def to_internal_value(self, data):
        return super().to_internal_value(data).upper()


class OpportunityResearchInput(serializers.Serializer):
    industry = serializers.CharField(max_length=200)
    regions = serializers.ListField(child=CountryCodeField(), required=False, default=list, max_length=30)
    keywords = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list,
                                     max_length=20)
    customer_segment = serializers.ChoiceField(choices=["SMB", "MID_MARKET", "ENTERPRISE", "ANY"], default="ANY")
    max_opportunities = serializers.IntegerField(min_value=1, max_value=20, default=5)
    max_ideas = serializers.IntegerField(min_value=1, max_value=10, default=3)
    language = serializers.CharField(**LANG)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class CustomerResearchInput(serializers.Serializer):
    software_idea_id = serializers.UUIDField()
    regions = serializers.ListField(child=CountryCodeField(), required=False, default=list, max_length=30)
    max_leads = serializers.IntegerField(min_value=1, max_value=200, default=25)
    channels = serializers.ListField(child=serializers.ChoiceField(choices=Channel.choices), required=False,
                                     default=lambda: [Channel.EMAIL])
    language = serializers.CharField(**LANG)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")

    def validate_software_idea_id(self, value):
        from apps.research.models import SoftwareIdea

        idea = SoftwareIdea.objects.filter(pk=value, workspace=self.context["workspace"]).first()
        if idea is None:
            raise serializers.ValidationError("Software idea not found in this workspace.")
        if idea.status != ReviewStatus.APPROVED:
            raise serializers.ValidationError("Software idea must be APPROVED before customer research.")
        return value


class LocationInput(serializers.Serializer):
    city = serializers.CharField(max_length=120)
    region = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    country_code = CountryCodeField()
    radius_km = serializers.IntegerField(min_value=1, max_value=100, default=10)
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)


class LeadDiscoveryInput(serializers.Serializer):
    location = LocationInput()
    categories = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list,
                                       max_length=30)
    max_businesses = serializers.IntegerField(min_value=1, max_value=200, default=25)
    checks = serializers.ListField(child=serializers.CharField(max_length=60), required=False, default=list)
    min_score = serializers.IntegerField(min_value=0, max_value=100, default=50)
    language = serializers.CharField(**LANG)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


INPUT_SERIALIZERS = {
    TaskType.SAAS_OPPORTUNITY_RESEARCH: OpportunityResearchInput,
    TaskType.SAAS_CUSTOMER_RESEARCH: CustomerResearchInput,
    TaskType.LOCAL_LEAD_DISCOVERY: LeadDiscoveryInput,
}


def validate_input(task_type: str, data: dict, *, workspace) -> dict:
    ser = INPUT_SERIALIZERS[task_type](data=data or {}, context={"workspace": workspace})
    if not ser.is_valid():
        raise serializers.ValidationError({"input": ser.errors})
    return _jsonable(ser.validated_data)


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    return value
