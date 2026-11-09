"""Inbound email events (bounces, complaints, unsubscribes, replies) — provider-neutral contract.

POST /api/v1/webhooks/email-events/
Headers: X-Webhook-Timestamp: <unix seconds>
         X-Webhook-Signature: sha256=<hex HMAC-SHA256(EMAIL_WEBHOOK_SECRET, "<timestamp>.<raw body>")>
Body:    {"events": [{"type": "BOUNCE|COMPLAINT|UNSUBSCRIBE|REPLY|DELIVERED", "email": "...",
                      "message_id": "<Message-ID we sent>", "bounce_type": "HARD|SOFT", "occurred_at": "..."}]}

Provider adapters (SES/Mailgun/Postmark → this format) are NOT implemented; a small relay or a future
adapter module must translate provider payloads. Disabled (503) until EMAIL_WEBHOOK_SECRET is set.
"""
import hashlib
import hmac
import time

from django.conf import settings
from django.db import transaction

from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.enums import LeadStatus, SuppressionReason, SuppressionSource, SuppressionType
from apps.common.normalize import normalize_email

from .models import OutreachMessage
from .services import add_suppression

MAX_SKEW_SECONDS = 300
SUPPRESSING = {"COMPLAINT": SuppressionReason.COMPLAINT, "UNSUBSCRIBE": SuppressionReason.OPT_OUT}


def verify_signature(raw_body: bytes, timestamp: str, signature: str, now: float | None = None) -> bool:
    secret = settings.EMAIL_WEBHOOK_SECRET
    if not secret or not timestamp or not signature.startswith("sha256="):
        return False
    try:
        if abs((now or time.time()) - int(timestamp)) > MAX_SKEW_SECONDS:
            return False  # replay protection
    except ValueError:
        return False
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))


def _messages_for(event) -> list[OutreachMessage]:
    """Our Message-ID identifies the exact message; otherwise every message sent to that address."""
    qs = OutreachMessage.objects.select_related("workspace", "lead")
    if event.get("message_id"):
        found = list(qs.filter(provider_message_id=event["message_id"]))
        if found:
            return found
    email = normalize_email(event.get("email"))
    return list(qs.filter(to_email__iexact=email).exclude(sent_at=None)) if email else []


@transaction.atomic
def process_events(events: list[dict]) -> dict:
    out = {"processed": 0, "suppressed": 0, "replies": 0, "unmatched": 0, "ignored": 0}
    actor = Actor.system()
    for ev in events:
        etype = ev["type"]
        if etype == "DELIVERED" or (etype == "BOUNCE" and ev.get("bounce_type") != "HARD"):
            out["ignored"] += 1  # soft bounces/deliveries carry no action in v1
            continue
        msgs = _messages_for(ev)
        if not msgs:
            out["unmatched"] += 1
            continue
        out["processed"] += 1
        email = normalize_email(ev.get("email")) or msgs[0].to_email
        if etype == "REPLY":
            for lead in {m.lead for m in msgs}:
                if lead.can_transition_to(LeadStatus.REPLIED):
                    lead.transition_to(LeadStatus.REPLIED)
                    lead.save(update_fields=["status", "updated_at"])
                    record("lead.replied", workspace=lead.workspace, actor=actor, target=lead)
                    out["replies"] += 1
            continue
        reason = SUPPRESSING.get(etype, SuppressionReason.BOUNCE)
        for ws in {m.workspace for m in msgs}:
            add_suppression(ws, type_=SuppressionType.EMAIL, value=email, reason=reason,
                            source=SuppressionSource.SYSTEM, actor=actor, note=f"Email provider event: {etype}")
            out["suppressed"] += 1
    return out
