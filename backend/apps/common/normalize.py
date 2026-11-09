import re
from urllib.parse import urlparse


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def email_domain(value: str | None) -> str:
    email = normalize_email(value)
    return email.rsplit("@", 1)[1] if "@" in email else ""


def normalize_domain(value: str | None) -> str:
    """'https://www.Example.com/x' -> 'example.com'."""
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = "http://" + value
    host = urlparse(value).hostname or ""
    return host[4:] if host.startswith("www.") else host


def normalize_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def normalize_phone(value: str | None) -> str:
    value = (value or "").strip()
    return ("+" if value.startswith("+") else "") + re.sub(r"\D", "", value)
