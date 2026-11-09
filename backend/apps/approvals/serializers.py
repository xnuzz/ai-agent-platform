from rest_framework import serializers

from apps.common.enums import ApprovalDecision

from .models import Approval


class ApprovalSerializer(serializers.ModelSerializer):
    decided_by_email = serializers.EmailField(source="decided_by.email", read_only=True, default=None)

    class Meta:
        model = Approval
        fields = ("id", "target_type", "target_id", "status", "research_task", "requested_by_type",
                  "requested_by_user", "requested_by_agent", "summary", "snapshot", "content_hash", "decided_by",
                  "decided_by_email", "decided_at", "decision_comment", "decision_options", "outcome",
                  "created_at", "updated_at")
        read_only_fields = fields


class SubmitForApprovalSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=ApprovalDecision.choices)
    comment = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")
    options = serializers.DictField(required=False, default=dict,
                                    help_text='SOFTWARE_IDEA only: {"auto_continue": true, '
                                              '"customer_research_input": {...}}')
