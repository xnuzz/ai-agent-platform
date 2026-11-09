from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.leads.models import Business, Lead
from apps.outreach.models import OutreachMessage, SuppressionEntry
from apps.privacy.services import purge_stale_contacts, subject_ref
from support.bundles import local_leads_bundle

from .conftest import LOCAL_INPUT

pytestmark = pytest.mark.django_db
EMAIL = "hello@bakery.test"


@pytest.fixture
def seeded(create_task, agent2, claim):
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    s = claim(agent2)
    s.results(local_leads_bundle())
    s.post("complete")


def test_export_returns_all_personal_data(api, seeded):
    r = api.post("/api/v1/privacy/export/", {"email": "Hello@Bakery.test"}, format="json")
    assert r.status_code == 200, r.content
    d = r.json()
    assert d["subject_email"] == EMAIL
    assert d["leads"][0]["contact_email"] == EMAIL and d["leads"][0]["business"] == "Corner Bakery"
    assert d["outreach_messages"][0]["subject"] == "Your website shows a security warning"
    assert d["businesses_using_this_address"][0]["name"] == "Corner Bakery"
    ev = AuditEvent.objects.get(action="privacy.exported")
    assert EMAIL not in str(ev.metadata) and ev.metadata["subject_ref"] == subject_ref(EMAIL)


def test_erase_redacts_and_suppresses(api, seeded):
    assert api.post("/api/v1/privacy/erase/", {"email": EMAIL}, format="json").status_code == 400  # confirm missing
    r = api.post("/api/v1/privacy/erase/", {"email": EMAIL, "confirm": True}, format="json")
    assert r.json() == {"leads_anonymized": 1, "messages_redacted": 1, "businesses_updated": 1, "suppressed": True}
    lead = Lead.objects.get()
    assert (lead.contact_email, lead.contact_phone, lead.legal_basis) == ("", "", "UNKNOWN")
    msg = OutreachMessage.objects.get()
    assert msg.status == "SUPPRESSED" and msg.to_email == "" and msg.body == "[erased]"
    assert Business.objects.get().email == ""
    entry = SuppressionEntry.objects.get()
    assert (entry.value, entry.reason) == (EMAIL, "LEGAL_REQUEST")
    for ev in AuditEvent.objects.filter(action__startswith="privacy."):
        assert EMAIL not in str(ev.metadata)
    # Export afterwards shows only the suppression entry (needed to never contact them again).
    d = api.post("/api/v1/privacy/export/", {"email": EMAIL}, format="json").json()
    assert d["leads"] == [] and d["outreach_messages"] == [] and len(d["suppression_entries"]) == 1


def test_privacy_endpoints_require_admin(developer_api, viewer_api, seeded):
    for client in (developer_api, viewer_api):
        assert client.post("/api/v1/privacy/export/", {"email": EMAIL}, format="json").status_code == 403
        assert client.post("/api/v1/privacy/erase/", {"email": EMAIL, "confirm": True},
                           format="json").status_code == 403


def test_retention_purges_only_stale_uncontacted_leads(api, seeded, workspace):
    Lead.objects.update(updated_at=timezone.now() - timedelta(days=400))
    assert purge_stale_contacts() == 1
    lead = Lead.objects.get()
    assert lead.contact_email == "" and lead.legal_basis == "UNKNOWN"
    msg = OutreachMessage.objects.get()
    assert msg.status == "CANCELLED" and msg.body == "[erased]"
    assert purge_stale_contacts() == 0  # idempotent


def test_retention_skips_contacted_recent_and_disabled(api, seeded, workspace):
    Lead.objects.update(updated_at=timezone.now() - timedelta(days=10))
    assert purge_stale_contacts() == 0  # recent
    Lead.objects.update(status="CONTACTED", updated_at=timezone.now() - timedelta(days=400))
    assert purge_stale_contacts() == 0  # contacted leads exempt
    Lead.objects.update(status="QUALIFIED")
    Lead.objects.update(updated_at=timezone.now() - timedelta(days=400))
    workspace.data_retention_days = 0
    workspace.save()
    assert purge_stale_contacts() == 0  # disabled
