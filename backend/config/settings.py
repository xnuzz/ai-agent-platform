"""Django settings. All secrets and environment-specific values come from env vars.

See /.env.example for the full list.
"""
from datetime import timedelta
from pathlib import Path
import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in env(name, default).split(",") if v.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
    "apps.audit",
    "apps.orchestration",
    "apps.research",
    "apps.leads",
    "apps.outreach",
    "apps.approvals",
    "apps.integrations",
    "apps.dashboard",
    "apps.privacy",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

_db = dj_database_url.config(env="DATABASE_URL", conn_max_age=60)
if not _db:
    raise ImproperlyConfigured("DATABASE_URL is required (PostgreSQL).")
DATABASES = {"default": _db}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- CORS (Vue dev server / deployed frontend) ---
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_HEADERS = (
    "accept", "authorization", "content-type", "x-workspace-id", "x-request-id",
)

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {"auth": "20/min", "public": "30/min", "webhook": "600/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Unified AI SaaS Platform API",
    "DESCRIPTION": "Central backend API. Contract source of truth: docs/API_CONTRACTS.md.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        f"{name}Enum": f"apps.common.enums.{name}"
        for name in (
            "AgentType", "SourceType", "TaskType", "TaskStatus", "ReviewStatus", "OpportunityStatus", "LeadStatus",
            "CampaignStatus", "MessageStatus", "ApprovalStatus", "ApprovalDecision", "ApprovalTargetType",
            "Channel", "LegalBasis", "ContactEmailType", "SuppressionType", "SuppressionReason",
            "SuppressionSource", "Role", "ActorType", "EvidenceSourceType", "IntegrationKind",
            "IntegrationProvider", "IntegrationStatus",
        )
    },
}

# --- Celery / Redis ---
CELERY_BROKER_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_ACKS_LATE = True
CELERY_BEAT_SCHEDULE = {
    "reap-expired-agent-leases": {"task": "orchestration.reap_expired_leases", "schedule": 60.0},
    "resume-active-campaigns": {"task": "outreach.resume_active_campaigns", "schedule": 300.0},
    "purge-stale-contacts": {"task": "privacy.purge_stale_contacts", "schedule": 86400.0},
}

# --- Email / outreach ---
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@localhost")

# Public base URL of the frontend; used to build unsubscribe links in outreach.
PUBLIC_APP_URL = env("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
# Public base URL of this API; used for RFC 8058 List-Unsubscribe headers.
PUBLIC_API_URL = env("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")

# Shared secret for HMAC-signed inbound email events (bounces/complaints/replies). Empty = endpoint disabled.
EMAIL_WEBHOOK_SECRET = env("EMAIL_WEBHOOK_SECRET", "")

# Fernet key for encrypting integration secrets at rest. Required to store secrets.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", "")

# --- Agent orchestration ---
AGENT_TASK_LEASE_SECONDS = int(env("AGENT_TASK_LEASE_SECONDS", "300"))
AGENT_RESULT_MAX_ITEMS_PER_SECTION = int(env("AGENT_RESULT_MAX_ITEMS_PER_SECTION", "500"))

# --- Security hardening for non-debug deployments ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "0"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
