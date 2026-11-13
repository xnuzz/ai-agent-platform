"""Test settings: ephemeral random secrets (never hardcoded), eager Celery, in-memory email."""
import os
import secrets

from cryptography.fernet import Fernet

os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_urlsafe(50))
os.environ.setdefault("FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DJANGO_DEBUG", "false")
os.environ.setdefault("DJANGO_SECURE_SSL_REDIRECT", "false")

from .settings import *  # noqa: E402,F401,F403

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ALLOWED_HOSTS = ["*"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SMTP_ALLOW_PRIVATE_HOSTS = True  # no DNS in tests; the guard has its own test
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"auth": "1000/min", "public": "1000/min", "webhook": "1000/min"}}  # noqa: F405
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405  (live_server threads must not hold connections)
