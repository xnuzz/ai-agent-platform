from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from apps.common.enums import Role

from .models import Membership, User, Workspace


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "date_joined")
        read_only_fields = fields


class WorkspaceSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    sender_identity_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = Workspace
        fields = (
            "id", "name", "slug", "role", "created_at",
            "sender_name", "sender_email", "reply_to_email", "sender_company", "sender_postal_address",
            "consent_required_countries", "daily_send_limit", "data_retention_days", "sender_identity_complete",
        )
        read_only_fields = ("id", "slug", "role", "created_at", "sender_identity_complete")

    def get_role(self, obj) -> str | None:
        user = self.context["request"].user
        m = next((m for m in obj.memberships.all() if m.user_id == user.id), None)
        return m.role if m else None

    def validate_consent_required_countries(self, value):
        if not isinstance(value, list) or any(not isinstance(c, str) or len(c) != 2 for c in value):
            raise serializers.ValidationError("Must be a list of ISO 3166-1 alpha-2 codes.")
        return [c.upper() for c in value]


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    email = serializers.EmailField(write_only=True)

    class Meta:
        model = Membership
        fields = ("id", "user", "email", "role", "created_at")
        read_only_fields = ("id", "user", "created_at")


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    workspace_name = serializers.CharField(max_length=200)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        validate_password(attrs["password"], User(email=attrs["email"], full_name=attrs.get("full_name", "")))
        return attrs

    @transaction.atomic
    def create(self, validated):
        user = User.objects.create_user(
            email=validated["email"], password=validated["password"], full_name=validated.get("full_name", "")
        )
        ws = Workspace.objects.create(name=validated["workspace_name"], created_by=user)
        Membership.objects.create(user=user, workspace=ws, role=Role.OWNER)
        return user
