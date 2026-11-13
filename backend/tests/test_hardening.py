"""Regression tests for the 2026-11-13 backend security/reliability audit fixes."""
import smtplib

import pytest
from django.core import mail

from apps.accounts.models import Membership, Workspace
from apps.common.enums import MessageStatus, Role
from apps.outreach import services
from apps.outreach.models import Campaign, OutreachMessage
from support.bundles import local_leads_bundle
from support.factories import add_member

from .conftest import LOCAL_INPUT, _client
from .test_email_webhooks import SECRET, post

pytestmark = pytest.mark.django_db


@pytest.fixture
def approved(api, create_task, agent2, claim):
    """Brief + campaign approved, campaign not launched yet."""
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    s = claim(agent2)
    rep = s.results(local_leads_bundle()).json()
    for a in rep["approvals_requested"]:
        api.post(f"/api/v1/approvals/{a['approval_id']}/decide/", {"decision": "APPROVED"}, format="json")
    return Campaign.objects.get(pk=rep["refs"]["campaigns"]["c1"])


def _activate(campaign):
    Campaign.objects.filter(pk=campaign.pk).update(status="ACTIVE")


def test_in_flight_sending_counts_against_daily_limit(approved, workspace):
    """Two concurrent batches must not both use the last unit of quota."""
    _activate(approved)
    msg = OutreachMessage.objects.get()
    other = OutreachMessage.objects.get(pk=msg.pk)
    other.pk, other.sequence_step, other.status = None, 2, MessageStatus.SENDING
    other.save()
    Workspace.objects.filter(pk=workspace.pk).update(daily_send_limit=1)
    assert services.send_message(msg.pk) == "deferred"
    assert OutreachMessage.objects.get(pk=msg.pk).status == MessageStatus.APPROVED and mail.outbox == []


def test_inactive_workspace_stops_sending_and_claiming(approved, workspace, create_task, agent2, claim):
    _activate(approved)
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    Workspace.objects.filter(pk=workspace.pk).update(is_active=False)
    assert services.send_message(OutreachMessage.objects.get().pk) == "skipped" and mail.outbox == []
    r = agent2.post("/api/v1/agent/tasks/claim/", {"worker_id": "w"}, format="json")
    assert r.status_code == 200 and r.json()["task"] is None


def test_provider_error_stores_no_recipient(approved, monkeypatch):
    _activate(approved)

    def refuse(self, *a, **k):
        raise smtplib.SMTPRecipientsRefused({"hello@bakery.test": (550, b"no such user hello@bakery.test")})

    monkeypatch.setattr(mail.EmailMessage, "send", refuse)
    msg = OutreachMessage.objects.get()
    assert services.send_message(msg.pk) == "failed"
    msg.refresh_from_db()
    assert msg.error == {"code": "provider_error", "message": "SMTPRecipientsRefused"}


def test_reply_needs_our_message_id(settings, approved, django_capture_on_commit_callbacks, api):
    settings.EMAIL_WEBHOOK_SECRET = SECRET
    with django_capture_on_commit_callbacks(execute=True):
        api.post(f"/api/v1/campaigns/{approved.pk}/launch/")
    msg = OutreachMessage.objects.get()
    assert post([{"type": "REPLY", "email": msg.to_email}]).json()["unmatched"] == 1
    assert msg.lead.__class__.objects.get(pk=msg.lead_id).status == "CONTACTED"


def test_admin_cannot_demote_or_remove_owner(workspace, owner):
    admin = add_member(workspace, "admin@example.com", Role.ADMIN)
    add_member(workspace, "owner2@example.com", Role.OWNER)  # last-owner guard is not what blocks this
    c = _client(admin, workspace)
    m = Membership.objects.get(workspace=workspace, user=owner)
    assert c.patch(f"/api/v1/members/{m.id}/", {"role": "VIEWER"}, format="json").status_code == 403
    assert c.delete(f"/api/v1/members/{m.id}/").status_code == 403
    assert Membership.objects.get(pk=m.pk).role == Role.OWNER


def test_oversized_body_rejected_before_parsing(client, settings):
    settings.MAX_REQUEST_BYTES = 100
    r = client.post("/api/v1/auth/token/", "x" * 101, content_type="application/json")
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_smtp_integration_refuses_internal_hosts_and_odd_ports(api, settings, monkeypatch):
    settings.SMTP_ALLOW_PRIVATE_HOSTS = False
    monkeypatch.setattr("socket.getaddrinfo", lambda host, port: [(2, 1, 6, "", ("169.254.169.254", 0))])
    body = {"kind": "EMAIL", "provider": "SMTP", "name": "x", "config": {"host": "metadata.internal", "port": 6379}}
    r = api.post("/api/v1/integrations/", body, format="json")
    assert r.status_code == 400
    errors = " ".join(r.json()["error"]["details"]["config"])
    assert "private or internal" in errors and "port must be one of" in errors
    monkeypatch.setattr("socket.getaddrinfo", lambda host, port: [(2, 1, 6, "", ("93.184.215.14", 0))])
    body["config"] = {"host": "smtp.example.com", "port": 587}
    assert api.post("/api/v1/integrations/", body, format="json").status_code == 201
