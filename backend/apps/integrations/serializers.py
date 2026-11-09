from rest_framework import serializers

from .models import Integration

SECRET_HINT_KEYS = {"password", "secret", "token", "api_key", "apikey", "key"}


class IntegrationSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    has_secret = serializers.BooleanField(read_only=True)

    class Meta:
        model = Integration
        fields = ("id", "kind", "provider", "name", "status", "config", "secret", "has_secret",
                  "last_verified_at", "created_at", "updated_at")
        read_only_fields = ("id", "has_secret", "last_verified_at", "created_at", "updated_at")

    def validate_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object.")
        leaked = [k for k in value if k.lower() in SECRET_HINT_KEYS]
        if leaked:
            raise serializers.ValidationError(f"Put credentials in 'secret', not config: {leaked}")
        return value

    def create(self, validated):
        secret = validated.pop("secret", None)
        obj = Integration(**validated)
        obj.set_secret(secret)
        obj.save()
        return obj

    def update(self, instance, validated):
        if "secret" in validated:
            instance.set_secret(validated.pop("secret"))
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.save()
        return instance
