import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.text import slugify

from apps.common.enums import Role
from apps.common.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self._create(email, password, **extra)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Workspace(TimeStampedModel):
    """Tenant boundary. Every business record belongs to exactly one workspace."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")

    # Outreach sender identity (required before any outbound email; ePrivacy/CAN-SPAM-style disclosure).
    sender_name = models.CharField(max_length=200, blank=True)
    sender_email = models.EmailField(blank=True)
    reply_to_email = models.EmailField(blank=True)
    sender_company = models.CharField(max_length=200, blank=True)
    sender_postal_address = models.TextField(blank=True)
    # Countries (ISO alpha-2) where the workspace requires CONSENT legal basis before emailing.
    consent_required_countries = models.JSONField(default=list, blank=True)
    daily_send_limit = models.PositiveIntegerField(default=100)

    def __str__(self):
        return self.name

    @property
    def sender_identity_complete(self) -> bool:
        return all([self.sender_name, self.sender_email, self.sender_company, self.sender_postal_address])

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:60] or "workspace"
            self.slug = f"{base}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)


class Membership(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.DEVELOPER)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "workspace"], name="uniq_membership")]
