from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor_user.email", read_only=True, default=None)

    class Meta:
        model = AuditEvent
        fields = ("id", "actor_type", "actor_user", "actor_email", "actor_agent", "action", "target_type",
                  "target_id", "metadata", "created_at")
        read_only_fields = fields
