import hashlib
import hmac
import json
import time

import pytest
from rest_framework.test import APIClient

from apps.common.enums import MessageStatus
from apps.leads.models import Lead
from apps.outreach.models import OutreachMessage, SuppressionEntry
from support.bundles import local_leads_bundle

from .conftest import LOCAL_INPUT

pytestmark = pytest.mark.django_db
SECRET = "test-webhook-secret"
URL = "/api/v1/webhooks/email-events/"


def post(events, *, secret=SECRET, ts=None):
    body = json.dumps({"events": events}).encode()
    ts = str(ts or int(time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return APIClient().post(URL, body, content_type="application/json",
                            HTTP_X_WEBHOOK_TIMESTAMP=ts, HTTP_X_WEBHOOK_SIGNATURE=f"sha256={sig}")


@pytest.fixture
def sent(settings, api, create_task, agent2, claim, django_capture_on_commit_callbacks):
    """One message actually sent through the pipeline (locmem backend)."""
    settings.EMAIL_WEBHOOK_SECRET = SECRET
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    s = claim(agent2)
    rep = s.results(local_leads_bundle()).json()
    for a in rep["approvals_requested"]:
        api.post(f"/api/v1/approvals/{a['approval_id']}/decide/", {"decision": "APPROVED"}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        api.post(f"/api/v1/campaigns/{rep['refs']['campaigns']['c1']}/launch/")
    msg = OutreachMessage.objects.get()
    assert msg.status == MessageStatus.SENT and msg.provider_message_id.startswith("<")
    return msg


def test_disabled_without_secret(settings, db):
    settings.EMAIL_WEBHOOK_SECRET = ""
    assert post([{"type": "COMPLAINT", "email": "a@b.test"}]).status_code == 503


def test_rejects_bad_signature_and_replay(sent):
    assert post([{"type": "COMPLAINT", "email": sent.to_email}], secret="wrong").status_code == 401
    assert post([{"type": "COMPLAINT", "email": sent.to_email}], ts=int(time.time()) - 3600).status_code == 401
    assert SuppressionEntry.objects.count() == 0


def test_hard_bounce_by_message_id_suppresses(sent):
    r = post([{"type": "BOUNCE", "bounce_type": "HARD", "message_id": sent.provider_message_id, "email": ""}])
    assert r.status_code == 200 and r.json()["suppressed"] == 1
    e = SuppressionEntry.objects.get()
    assert (e.value, e.reason, e.source) == ("hello@bakery.test", "BOUNCE", "SYSTEM")


def test_soft_bounce_and_delivered_are_ignored(sent):
    r = post([{"type": "BOUNCE", "bounce_type": "SOFT", "email": sent.to_email}, {"type": "DELIVERED",
                                                                                    "email": sent.to_email}])
    assert r.json()["ignored"] == 2 and SuppressionEntry.objects.count() == 0


def test_complaint_by_email_and_idempotent(sent):
    for _ in range(2):
        assert post([{"type": "COMPLAINT", "email": "HELLO@bakery.test"}]).status_code == 200
    assert SuppressionEntry.objects.get().reason == "COMPLAINT"


def test_reply_marks_lead_replied(sent):
    r = post([{"type": "REPLY", "message_id": sent.provider_message_id}])
    assert r.json()["replies"] == 1 and Lead.objects.get().status == "REPLIED"


def test_unknown_address_is_unmatched(sent):
    assert post([{"type": "COMPLAINT", "email": "stranger@nowhere.test"}]).json()["unmatched"] == 1
    assert SuppressionEntry.objects.count() == 0
