from rest_framework import serializers

from apps.common.enums import OpportunityStatus

from .models import Evidence, Opportunity, SoftwareIdea


class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidence
        fields = ("id", "research_task", "url", "title", "source_type", "excerpt", "retrieved_at", "metadata",
                  "created_at")
        read_only_fields = fields


class OpportunitySerializer(serializers.ModelSerializer):
    evidence_ids = serializers.PrimaryKeyRelatedField(source="evidence", many=True, read_only=True)

    class Meta:
        model = Opportunity
        fields = ("id", "research_task", "title", "problem_statement", "industry", "target_segment",
                  "pain_severity", "score", "competitors", "market_signals", "status", "evidence_ids",
                  "created_at", "updated_at")
        read_only_fields = tuple(f for f in fields if f != "status")


class OpportunityStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OpportunityStatus.choices)


class SoftwareIdeaSerializer(serializers.ModelSerializer):
    evidence_ids = serializers.PrimaryKeyRelatedField(source="evidence", many=True, read_only=True)

    class Meta:
        model = SoftwareIdea
        fields = ("id", "research_task", "opportunity", "name", "summary", "problem", "solution",
                  "target_customers", "key_features", "pricing_model", "differentiation", "risks", "mvp_scope",
                  "score", "status", "evidence_ids", "approved_at", "approved_by", "created_at", "updated_at")
        read_only_fields = ("id", "research_task", "opportunity", "score", "status", "evidence_ids",
                            "approved_at", "approved_by", "created_at", "updated_at")
