from rest_framework import serializers

from apps.common.enums import SuppressionReason, SuppressionType

from .models import Campaign, OutreachMessage, SuppressionEntry


class CampaignSerializer(serializers.ModelSerializer):
    message_counts = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = ("id", "name", "source", "research_task", "software_idea", "project_brief", "channel", "offer",
                  "status", "approved_at", "approved_by", "launched_at", "completed_at", "message_counts",
                  "created_at", "updated_at")
        read_only_fields = ("id", "source", "research_task", "software_idea", "project_brief", "channel",
                            "status", "approved_at", "approved_by", "launched_at", "completed_at",
                            "message_counts", "created_at", "updated_at")

    def get_message_counts(self, obj) -> dict:
        counts: dict = {}
        for status in obj.messages.values_list("status", flat=True):
            counts[status] = counts.get(status, 0) + 1
        return counts


class OutreachMessageSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="lead.business.name", read_only=True)

    class Meta:
        model = OutreachMessage
        fields = ("id", "campaign", "lead", "business_name", "channel", "sequence_step", "to_email", "subject",
                  "body", "language", "status", "sent_at", "error", "created_at", "updated_at")
        read_only_fields = ("id", "campaign", "lead", "business_name", "channel", "sequence_step", "to_email",
                            "status", "sent_at", "error", "created_at", "updated_at")


class SuppressionEntrySerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(choices=SuppressionType.choices)
    reason = serializers.ChoiceField(choices=SuppressionReason.choices, default=SuppressionReason.MANUAL)

    class Meta:
        model = SuppressionEntry
        fields = ("id", "type", "value", "reason", "source", "note", "created_by", "created_at")
        read_only_fields = ("id", "source", "created_by", "created_at")


class UnsubscribeInfoSerializer(serializers.Serializer):
    email_masked = serializers.CharField()
    sender = serializers.CharField()
    already_unsubscribed = serializers.BooleanField()
