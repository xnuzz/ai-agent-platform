from rest_framework import serializers

from apps.common.enums import LeadStatus

from .models import Business, Lead, ProjectBrief


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ("id", "name", "website", "domain", "email", "phone", "address_line1", "city", "region",
                  "postal_code", "country_code", "latitude", "longitude", "category", "description",
                  "source_data", "created_at", "updated_at")
        read_only_fields = fields


class LeadSerializer(serializers.ModelSerializer):
    business = BusinessSerializer(read_only=True)
    evidence_ids = serializers.PrimaryKeyRelatedField(source="evidence", many=True, read_only=True)
    is_suppressed = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = ("id", "business", "research_task", "source", "software_idea", "status", "score",
                  "qualification_notes", "problems", "contact_name", "contact_role", "contact_email",
                  "contact_phone", "contact_email_type", "legal_basis", "legal_basis_note", "evidence_ids",
                  "is_suppressed", "created_at", "updated_at")
        read_only_fields = ("id", "business", "research_task", "source", "software_idea", "status", "score",
                            "problems", "evidence_ids", "is_suppressed", "created_at", "updated_at")

    def get_is_suppressed(self, obj) -> bool:
        from apps.outreach.services import is_suppressed

        return is_suppressed(obj.workspace_id, email=obj.recipient_email, phone=obj.contact_phone)


class LeadStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LeadStatus.choices)


class ProjectBriefSerializer(serializers.ModelSerializer):
    evidence_ids = serializers.PrimaryKeyRelatedField(source="evidence", many=True, read_only=True)

    class Meta:
        model = ProjectBrief
        fields = ("id", "lead", "research_task", "title", "summary", "problems", "proposed_solution",
                  "scope_items", "tech_stack", "estimated_effort_hours_min", "estimated_effort_hours_max",
                  "estimated_budget_min", "estimated_budget_max", "currency", "status", "evidence_ids",
                  "approved_at", "approved_by", "created_at", "updated_at")
        read_only_fields = ("id", "lead", "research_task", "problems", "status", "evidence_ids", "approved_at",
                            "approved_by", "created_at", "updated_at")
