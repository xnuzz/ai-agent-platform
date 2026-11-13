import ipaddress
import socket

from django.conf import settings
from rest_framework import serializers

from .models import Integration

SECRET_HINT_KEYS = {"password", "secret", "token", "api_key", "apikey", "key"}
SMTP_PORTS = {25, 465, 587, 2525}


def smtp_config_errors(config: dict) -> list[str]:
    """SMTP integrations are dialled from the Celery worker: refuse non-SMTP ports and (unless allowed) hosts that
    resolve to private/loopback/link-local addresses, so a workspace cannot probe the internal network."""
    errors = []
    try:
        if int(config.get("port", 587)) not in SMTP_PORTS:
            errors.append(f"port must be one of {sorted(SMTP_PORTS)}")
    except (TypeError, ValueError):
        errors.append("port must be a number")
    host = str(config.get("host") or "").strip()
    if not host:
        return [*errors, "host is required"]
    if settings.SMTP_ALLOW_PRIVATE_HOSTS:
        return errors
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except (OSError, UnicodeError):
        return [*errors, "host does not resolve"]
    if any(not ipaddress.ip_address(a.split("%")[0]).is_global for a in addrs):
        errors.append("host resolves to a private or internal address")
    return errors


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

    def validate(self, attrs):
        provider = attrs.get("provider", getattr(self.instance, "provider", None))
        config = attrs.get("config", getattr(self.instance, "config", None)) or {}
        if provider == "SMTP" and ("config" in attrs or self.instance is None):
            errors = smtp_config_errors(config)
            if errors:
                raise serializers.ValidationError({"config": errors})
        return attrs

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
