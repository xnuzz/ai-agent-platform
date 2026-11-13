"""Outreach execution. The ONLY code path that sends outbound communication.

Every send re-checks: approval pin (hash), campaign state, suppression, legal basis, sender identity.
"""
import logging
from datetime import datetime, time, timezone as dt_timezone
from email.utils import make_msgid

from django.conf import settings
from django.core import mail, signing
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.enums import (
    CampaignStatus, IntegrationKind, IntegrationProvider, IntegrationStatus, LeadStatus, LegalBasis, MessageStatus,
    ReviewStatus, SuppressionSource, SuppressionType,
)
from apps.common.exceptions import ComplianceBlocked, InvalidStateTransition
from apps.common.normalize import email_domain, normalize_domain, normalize_email, normalize_phone

from .models import Campaign, OutreachMessage, SuppressionEntry

logger = logging.getLogger(__name__)
UNSUBSCRIBE_SALT = "outreach.unsubscribe.v1"
PENDING_MESSAGE_STATES = [MessageStatus.DRAFT, MessageStatus.WAITING_FOR_APPROVAL, MessageStatus.APPROVED]
# Recipient country -> accepted subject prefixes marking an unsolicited e-mail as commercial (case-insensitive).
# BG: meant to keep unsolicited commercial e-mail identifiable as such (ЗЕТ чл. 6). Conservative platform convention,
# NOT a validated legal reading — see docs/DECISIONS.md ADR-018.
COMMERCIAL_SUBJECT_MARKERS = {"BG": ("търговско предложение", "търговско съобщение")}


# ---------------------------------------------------------------- suppression

def normalize_suppression_value(type_: str, value: str) -> str:
    if type_ == SuppressionType.EMAIL:
        return normalize_email(value)
    if type_ == SuppressionType.DOMAIN:
        return normalize_domain(value)
    if type_ == SuppressionType.PHONE:
        return normalize_phone(value)
    raise ValueError(type_)


def is_suppressed(workspace_id, *, email: str = "", phone: str = "") -> bool:
    q = Q()
    if email:
        q |= Q(type=SuppressionType.EMAIL, value=normalize_email(email))
        q |= Q(type=SuppressionType.DOMAIN, value=email_domain(email))
    if phone:
        q |= Q(type=SuppressionType.PHONE, value=normalize_phone(phone))
    if not q:
        return False
    return SuppressionEntry.objects.filter(q, workspace_id=workspace_id).exists()


@transaction.atomic
def add_suppression(workspace, *, type_: str, value: str, reason: str, source: str, actor: Actor,
                    note: str = "") -> SuppressionEntry:
    value = normalize_suppression_value(type_, value)
    entry, created = SuppressionEntry.objects.get_or_create(
        workspace=workspace, type=type_, value=value,
        defaults={"reason": reason, "source": source, "note": note,
                  "created_by": actor.user if actor.is_user else None},
    )
    if created:
        record("suppression.created", workspace=workspace, actor=actor, target=entry,
               metadata={"type": type_, "reason": reason, "source": source})
    _suppress_pending_messages(workspace, type_, value, actor)
    return entry


def _suppress_pending_messages(workspace, type_, value, actor):
    qs = OutreachMessage.objects.filter(workspace=workspace, status__in=PENDING_MESSAGE_STATES)
    if type_ == SuppressionType.EMAIL:
        qs = qs.filter(to_email__iexact=value)
    elif type_ == SuppressionType.DOMAIN:
        qs = qs.filter(to_email__iendswith="@" + value)
    elif type_ == SuppressionType.PHONE:
        qs = qs.filter(lead__contact_phone=value)
    for msg in qs.select_for_update():
        msg.transition_to(MessageStatus.SUPPRESSED)
        msg.save(update_fields=["status", "updated_at"])
        record("outreach_message.suppressed", workspace=workspace, actor=actor, target=msg)


def make_unsubscribe_token(message: OutreachMessage) -> str:
    return signing.dumps({"w": str(message.workspace_id), "e": message.to_email, "m": str(message.id)},
                         salt=UNSUBSCRIBE_SALT, compress=True)


def read_unsubscribe_token(token: str) -> dict:
    return signing.loads(token, salt=UNSUBSCRIBE_SALT)  # raises signing.BadSignature


@transaction.atomic
def process_unsubscribe(token: str) -> SuppressionEntry:
    from apps.accounts.models import Workspace

    data = read_unsubscribe_token(token)
    workspace = Workspace.objects.get(id=data["w"])
    from apps.common.enums import SuppressionReason

    return add_suppression(workspace, type_=SuppressionType.EMAIL, value=data["e"],
                           reason=SuppressionReason.OPT_OUT, source=SuppressionSource.UNSUBSCRIBE_LINK,
                           actor=Actor.system(), note=f"Unsubscribe link, message {data.get('m')}")


# ---------------------------------------------------------------- campaign lifecycle

def assert_campaign_launchable(campaign: Campaign) -> None:
    errors = []
    if campaign.software_idea_id and campaign.software_idea.status != ReviewStatus.APPROVED:
        errors.append("software_idea_not_approved")
    if campaign.project_brief_id and campaign.project_brief.status != ReviewStatus.APPROVED:
        errors.append("project_brief_not_approved")
    if not campaign.workspace.sender_identity_complete:
        errors.append("sender_identity_incomplete")
    approved = campaign.messages.filter(status=MessageStatus.APPROVED).select_related("lead__business")
    if any(commercial_marker_missing(m) for m in approved):
        errors.append("commercial_subject_marker_missing")  # caught before launch, not as FAILED sends
    if errors:
        raise ComplianceBlocked("Campaign cannot be launched.", details={"reasons": errors})


@transaction.atomic
def launch_campaign(campaign: Campaign, actor: Actor) -> Campaign:
    campaign = Campaign.objects.select_for_update(of=("self",)).select_related(
        "workspace", "software_idea", "project_brief").get(pk=campaign.pk)
    if campaign.status not in (CampaignStatus.APPROVED, CampaignStatus.PAUSED):
        raise InvalidStateTransition(f"Campaign in {campaign.status} cannot be launched.")
    assert_campaign_launchable(campaign)
    campaign.transition_to(CampaignStatus.ACTIVE)
    campaign.launched_at = campaign.launched_at or timezone.now()
    campaign.save(update_fields=["status", "launched_at", "updated_at"])
    record("campaign.launched", workspace=campaign.workspace, actor=actor, target=campaign)
    from .tasks import send_campaign_batch

    transaction.on_commit(lambda: send_campaign_batch.delay(str(campaign.pk)))
    return campaign


@transaction.atomic
def set_campaign_status(campaign: Campaign, new_status: str, actor: Actor) -> Campaign:
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    campaign.transition_to(new_status)
    campaign.save(update_fields=["status", "updated_at"])
    if new_status == CampaignStatus.CANCELLED:
        for msg in campaign.messages.select_for_update().filter(status__in=PENDING_MESSAGE_STATES):
            msg.transition_to(MessageStatus.CANCELLED)
            msg.save(update_fields=["status", "updated_at"])
    record(f"campaign.{new_status.lower()}", workspace=campaign.workspace, actor=actor, target=campaign)
    return campaign


# ---------------------------------------------------------------- sending

def commercial_marker_missing(msg: OutreachMessage) -> bool:
    markers = COMMERCIAL_SUBJECT_MARKERS.get((msg.lead.business.country_code or "").upper())
    return bool(markers) and not (msg.subject or "").strip().lower().startswith(markers)


def compliance_errors(msg: OutreachMessage) -> list[str]:
    ws, lead = msg.workspace, msg.lead
    errors = []
    if not ws.sender_identity_complete:
        errors.append("sender_identity_incomplete")
    if not msg.to_email:
        errors.append("no_recipient")
    if lead.status in (LeadStatus.DISQUALIFIED, LeadStatus.ARCHIVED, LeadStatus.LOST):
        errors.append("lead_not_contactable")
    if lead.legal_basis == LegalBasis.UNKNOWN:
        errors.append("legal_basis_unknown")
    country = (lead.business.country_code or "").upper()
    required = {c.upper() for c in (ws.consent_required_countries or [])}
    if country in required and lead.legal_basis != LegalBasis.CONSENT:
        errors.append("consent_required")
    if commercial_marker_missing(msg):
        errors.append("commercial_subject_marker_missing")
    return errors


def _used_today(workspace) -> int:
    """Daily quota used: SENT today plus in-flight SENDING (a stuck SENDING may have gone out)."""
    start = datetime.combine(timezone.now().date(), time.min, tzinfo=dt_timezone.utc)
    return OutreachMessage.objects.filter(
        Q(status=MessageStatus.SENT, sent_at__gte=start) | Q(status=MessageStatus.SENDING, updated_at__gte=start),
        workspace=workspace).count()


def _email_connection(workspace):
    from apps.integrations.models import Integration

    integ = Integration.objects.filter(workspace=workspace, kind=IntegrationKind.EMAIL,
                                       provider=IntegrationProvider.SMTP, status=IntegrationStatus.ACTIVE).first()
    if integ is None:
        return mail.get_connection()
    cfg = integ.config
    return mail.get_connection(
        "django.core.mail.backends.smtp.EmailBackend", host=cfg.get("host"), port=int(cfg.get("port", 587)),
        username=cfg.get("username", ""), password=integ.get_secret() or "", use_tls=bool(cfg.get("use_tls", True)),
        timeout=30,
    )


def build_email(msg: OutreachMessage, connection=None) -> mail.EmailMessage:
    ws = msg.workspace
    token = make_unsubscribe_token(msg)
    page_url = f"{settings.PUBLIC_APP_URL}/unsubscribe/{token}"
    api_url = f"{settings.PUBLIC_API_URL}/api/v1/public/unsubscribe/{token}/"
    footer = (f"\n\n--\n{ws.sender_name}, {ws.sender_company}\n{ws.sender_postal_address}\n"
              f"You received this one-time business message because of your company's public listing. "
              f"To opt out of further messages: {page_url}")
    return mail.EmailMessage(
        subject=msg.subject, body=msg.body + footer, from_email=f"{ws.sender_name} <{ws.sender_email}>",
        to=[msg.to_email], reply_to=[ws.reply_to_email or ws.sender_email], connection=connection,
        headers={"List-Unsubscribe": f"<{api_url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                 "Message-ID": make_msgid(domain=(ws.sender_email.rsplit("@", 1)[-1] or None))},
    )


def send_message(message_id) -> str:
    """Send one approved message. At-most-once: status moves to SENDING (committed) before the SMTP call."""
    actor = Actor.system()
    with transaction.atomic():
        msg = (OutreachMessage.objects.select_for_update(of=("self",))
               .select_related("campaign", "lead", "lead__business", "workspace").get(pk=message_id))
        if (msg.status != MessageStatus.APPROVED or msg.campaign.status != CampaignStatus.ACTIVE
                or not msg.workspace.is_active):
            return "skipped"
        if not msg.approved_hash or msg.compute_hash() != msg.approved_hash:
            return _fail(msg, actor, "content_changed_after_approval")
        if is_suppressed(msg.workspace_id, email=msg.to_email, phone=msg.lead.contact_phone):
            msg.transition_to(MessageStatus.SUPPRESSED)
            msg.save(update_fields=["status", "updated_at"])
            record("outreach_message.suppressed", workspace=msg.workspace, actor=actor, target=msg)
            return "suppressed"
        errors = compliance_errors(msg)
        if errors:
            return _fail(msg, actor, "compliance_blocked", errors)
        # Reserve quota under a workspace row lock so concurrent batches cannot overrun daily_send_limit.
        from apps.accounts.models import Workspace

        ws = Workspace.objects.select_for_update().get(pk=msg.workspace_id)
        if _used_today(ws) >= ws.daily_send_limit:
            return "deferred"  # stays APPROVED; resume_active_campaigns retries tomorrow
        msg.transition_to(MessageStatus.SENDING)
        msg.save(update_fields=["status", "updated_at"])

    try:
        email = build_email(msg, connection=_email_connection(msg.workspace))
        email.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 - provider errors are recorded, never retried blindly
        # Never store/log str(exc): SMTP errors echo recipient addresses and internal hosts.
        smtp_code = getattr(exc, "smtp_code", None)
        summary = type(exc).__name__ + (f" (SMTP {smtp_code})" if smtp_code else "")
        logger.warning("Outreach send failed for %s: %s", msg.pk, summary)
        with transaction.atomic():
            msg.refresh_from_db()
            msg.status = MessageStatus.FAILED
            msg.error = {"code": "provider_error", "message": summary}
            msg.save(update_fields=["status", "error", "updated_at"])
            record("outreach_message.failed", workspace=msg.workspace, actor=actor, target=msg,
                   metadata=msg.error)
        return "failed"

    with transaction.atomic():
        msg.transition_to(MessageStatus.SENT)
        msg.sent_at = timezone.now()
        msg.provider_message_id = email.extra_headers.get("Message-ID", "")
        msg.save(update_fields=["status", "sent_at", "provider_message_id", "updated_at"])
        lead = msg.lead
        if lead.can_transition_to(LeadStatus.CONTACTED):
            lead.transition_to(LeadStatus.CONTACTED)
            lead.save(update_fields=["status", "updated_at"])
        record("outreach_message.sent", workspace=msg.workspace, actor=actor, target=msg,
               metadata={"campaign_id": str(msg.campaign_id), "lead_id": str(msg.lead_id)})
    return "sent"


def _fail(msg, actor, code, reasons=None) -> str:
    msg.transition_to(MessageStatus.FAILED)
    msg.error = {"code": code, "reasons": reasons or []}
    msg.save(update_fields=["status", "error", "updated_at"])
    record("outreach_message.blocked", workspace=msg.workspace, actor=actor, target=msg, metadata=msg.error)
    return "failed"


def run_campaign_batch(campaign_id) -> dict:
    campaign = Campaign.objects.select_related("workspace").get(pk=campaign_id)
    if campaign.status != CampaignStatus.ACTIVE:
        return {"status": campaign.status, "sent": 0}
    if not campaign.workspace.is_active:
        return {"status": "workspace_inactive", "sent": 0}
    remaining = max(campaign.workspace.daily_send_limit - _used_today(campaign.workspace), 0)
    ids = list(campaign.messages.filter(status=MessageStatus.APPROVED).order_by("created_at")
               .values_list("id", flat=True)[:remaining])
    results = {}
    for mid in ids:
        outcome = send_message(mid)
        results[outcome] = results.get(outcome, 0) + 1
        if outcome == "deferred":
            break
    if not campaign.messages.filter(status__in=[MessageStatus.APPROVED, MessageStatus.SENDING]).exists():
        with transaction.atomic():
            c = Campaign.objects.select_for_update().get(pk=campaign_id)
            if c.status == CampaignStatus.ACTIVE:
                c.transition_to(CampaignStatus.COMPLETED)
                c.completed_at = timezone.now()
                c.save(update_fields=["status", "completed_at", "updated_at"])
                record("campaign.completed", workspace=c.workspace, actor=Actor.system(), target=c,
                       metadata=results)
    return results
