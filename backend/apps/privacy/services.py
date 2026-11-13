"""GDPR data-subject tooling (docs/DATABASE_SCHEMA.md §Personal data).

A data subject is identified by an email address within one workspace. Personal data lives in
Lead.contact_*, OutreachMessage.to_email/subject/body, Business.email (when it is the address) and
SuppressionEntry. Erasure keeps an EMAIL suppression entry (LEGAL_REQUEST) on purpose: it is the only
way to honour "never contact me again", and it is the minimum data needed for that.
"""
import hashlib
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record
from apps.common.actor import Actor
from apps.common.enums import LeadStatus, LegalBasis, MessageStatus, SuppressionReason, SuppressionSource, SuppressionType
from apps.common.normalize import normalize_email
from apps.leads.models import Business, Lead
from apps.outreach.models import OutreachMessage, SuppressionEntry

REDACTED = "[erased]"
# Leads that were contacted keep their contact data until the relationship ends (WON is a client).
RETENTION_EXEMPT = [LeadStatus.CONTACTED, LeadStatus.REPLIED, LeadStatus.WON]
PENDING = [MessageStatus.DRAFT, MessageStatus.WAITING_FOR_APPROVAL, MessageStatus.APPROVED]


def subject_ref(email: str) -> str:
    """Stable pseudonymous reference for audit logs (never store the address itself in the audit trail)."""
    return hashlib.sha256(normalize_email(email).encode()).hexdigest()[:16]


def _leads(workspace, email):
    return Lead.objects.filter(workspace=workspace, contact_email__iexact=email).select_related("business")


def _messages(workspace, email):
    return OutreachMessage.objects.filter(workspace=workspace, to_email__iexact=email).select_related(
        "campaign", "lead__business")


def export_subject(workspace, email: str, actor: Actor) -> dict:
    email = normalize_email(email)
    data = {
        "subject_email": email,
        "workspace": {"id": str(workspace.id), "name": workspace.name},
        "exported_at": timezone.now().isoformat(),
        "leads": [{
            "id": str(l.id), "business": l.business.name, "source": l.source, "status": l.status,
            "contact_name": l.contact_name, "contact_role": l.contact_role, "contact_email": l.contact_email,
            "contact_phone": l.contact_phone, "legal_basis": l.legal_basis, "legal_basis_note": l.legal_basis_note,
            "qualification_notes": l.qualification_notes, "created_at": l.created_at.isoformat(),
        } for l in _leads(workspace, email)],
        "outreach_messages": [{
            "id": str(m.id), "campaign": m.campaign.name, "business": m.lead.business.name, "status": m.status,
            "subject": m.subject, "body": m.body, "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        } for m in _messages(workspace, email)],
        "businesses_using_this_address": [{"id": str(b.id), "name": b.name, "website": b.website}
                                          for b in Business.objects.filter(workspace=workspace, email__iexact=email)],
        "suppression_entries": [{"type": s.type, "reason": s.reason, "source": s.source,
                                 "created_at": s.created_at.isoformat()}
                                for s in SuppressionEntry.objects.filter(workspace=workspace, type=SuppressionType.EMAIL,
                                                                         value=email)],
    }
    record("privacy.exported", workspace=workspace, actor=actor,
           metadata={"subject_ref": subject_ref(email), "leads": len(data["leads"]),
                     "messages": len(data["outreach_messages"])})
    return data


def _anonymize_lead(lead: Lead) -> None:
    lead.contact_name = lead.contact_role = lead.contact_email = lead.contact_phone = ""
    lead.legal_basis_note = ""
    lead.legal_basis = LegalBasis.UNKNOWN  # nothing can be sent without a fresh, recorded basis
    lead.save(update_fields=["contact_name", "contact_role", "contact_email", "contact_phone",
                             "legal_basis_note", "legal_basis", "updated_at"])


def _redact_message(msg: OutreachMessage) -> None:
    msg.to_email, msg.subject, msg.body, msg.error = "", REDACTED, REDACTED, {}
    msg.save(update_fields=["to_email", "subject", "body", "error", "updated_at"])


@transaction.atomic
def erase_subject(workspace, email: str, actor: Actor) -> dict:
    """Right to erasure (Art. 17). Suppress first (cancels pending sends), then redact everywhere."""
    from apps.outreach.services import add_suppression

    email = normalize_email(email)
    add_suppression(workspace, type_=SuppressionType.EMAIL, value=email, reason=SuppressionReason.LEGAL_REQUEST,
                    source=SuppressionSource.USER, actor=actor, note="GDPR erasure request")
    leads = list(_leads(workspace, email))
    for lead in leads:
        _anonymize_lead(lead)
    msgs = list(_messages(workspace, email))
    for msg in msgs:
        _redact_message(msg)
    businesses = Business.objects.filter(workspace=workspace, email__iexact=email).update(
        email="", updated_at=timezone.now())
    result = {"leads_anonymized": len(leads), "messages_redacted": len(msgs), "businesses_updated": businesses,
              "suppressed": True}
    record("privacy.erased", workspace=workspace, actor=actor, metadata={"subject_ref": subject_ref(email), **result})
    return result


def purge_stale_contacts(now=None) -> int:
    """Retention job: anonymize contact data on leads idle longer than the workspace's data_retention_days."""
    from apps.accounts.models import Workspace

    now = now or timezone.now()
    total = 0
    for ws in Workspace.objects.filter(is_active=True, data_retention_days__gt=0):
        cutoff = now - timedelta(days=ws.data_retention_days)
        with transaction.atomic():
            leads = list(Lead.objects.select_for_update().filter(workspace=ws, updated_at__lt=cutoff)
                         .exclude(status__in=RETENTION_EXEMPT)
                         .filter(~Q(contact_email="") | ~Q(contact_name="") | ~Q(contact_phone="")))
            for lead in leads:
                for msg in OutreachMessage.objects.filter(lead=lead).exclude(status=MessageStatus.SENT):
                    if msg.status in PENDING:
                        msg.transition_to(MessageStatus.CANCELLED)
                        msg.save(update_fields=["status", "updated_at"])
                    _redact_message(msg)
                _anonymize_lead(lead)
            if leads:
                record("privacy.retention_purged", workspace=ws, actor=Actor.system(),
                       metadata={"leads": len(leads), "retention_days": ws.data_retention_days})
        total += len(leads)
    return total
