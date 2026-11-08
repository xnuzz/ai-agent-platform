import pytest
from django.core import mail

from apps.accounts.models import Workspace
from apps.approvals.models import Approval
from apps.leads.models import Lead
from apps.outreach.models import OutreachMessage, SuppressionEntry
from apps.outreach.services import make_unsubscribe_token
from support.factories import customer_bundle, local_leads_bundle

from .conftest import LOCAL_INPUT

pytestmark = pytest.mark.django_db


@pytest.fixture
def local_pending(create_task, agent2, claim):
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    s = claim(agent2)
    rep = s.results(local_leads_bundle()).json()
    s.post("complete")
    return {a["target_type"]: a for a in rep["approvals_requested"]}, rep


def _decide(api, approval_id, decision="APPROVED"):
    r = api.post(f"/api/v1/approvals/{approval_id}/decide/", {"decision": decision}, format="json")
    assert r.status_code == 200, r.content


def _launch(api, campaign_id, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        return api.post(f"/api/v1/campaigns/{campaign_id}/launch/")


def test_launch_requires_campaign_approval(api, local_pending):
    approvals, rep = local_pending
    cid = rep["refs"]["campaigns"]["c1"]
    r = api.post(f"/api/v1/campaigns/{cid}/launch/")
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_state"


def test_launch_requires_project_brief_approval(api, local_pending):
    approvals, rep = local_pending
    _decide(api, approvals["CAMPAIGN"]["approval_id"])
    r = api.post(f"/api/v1/campaigns/{rep['refs']['campaigns']['c1']}/launch/")
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reasons"] == ["project_brief_not_approved"]


def test_launch_requires_sender_identity(api, local_pending, workspace):
    approvals, rep = local_pending
    for a in approvals.values():
        _decide(api, a["approval_id"])
    Workspace.objects.filter(pk=workspace.pk).update(sender_postal_address="")
    r = api.post(f"/api/v1/campaigns/{rep['refs']['campaigns']['c1']}/launch/")
    assert r.json()["error"]["details"]["reasons"] == ["sender_identity_incomplete"]


def test_full_send_with_footer_and_unsubscribe(api, local_pending, django_capture_on_commit_callbacks):
    approvals, rep = local_pending
    for a in approvals.values():
        _decide(api, a["approval_id"])
    cid = rep["refs"]["campaigns"]["c1"]
    r = _launch(api, cid, django_capture_on_commit_callbacks)
    assert r.status_code == 200, r.content
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == ["hello@bakery.test"]
    assert "1 Test Street" in email.body and "/unsubscribe/" in email.body
    assert email.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    msg = OutreachMessage.objects.get()
    assert msg.status == "SENT" and msg.lead.status == "CONTACTED"
    assert api.get(f"/api/v1/campaigns/{cid}/").json()["status"] == "COMPLETED"

    # Recipient opts out via the public link (no auth).
    from rest_framework.test import APIClient

    token = make_unsubscribe_token(msg)
    pub = APIClient()
    assert pub.get(f"/api/v1/public/unsubscribe/{token}/").json()["already_unsubscribed"] is False
    assert pub.post(f"/api/v1/public/unsubscribe/{token}/").status_code == 200
    entry = SuppressionEntry.objects.get()
    assert (entry.type, entry.value, entry.source) == ("EMAIL", "hello@bakery.test", "UNSUBSCRIBE_LINK")
    assert pub.get("/api/v1/public/unsubscribe/forged/").status_code == 404


def test_send_time_suppression(api, local_pending, django_capture_on_commit_callbacks):
    approvals, rep = local_pending
    for a in approvals.values():
        _decide(api, a["approval_id"])
    api.post("/api/v1/suppression-entries/", {"type": "EMAIL", "value": "hello@bakery.test"}, format="json")
    assert OutreachMessage.objects.get().status == "SUPPRESSED"  # pending messages suppressed immediately
    _launch(api, rep["refs"]["campaigns"]["c1"], django_capture_on_commit_callbacks)
    assert mail.outbox == []


def test_unknown_legal_basis_blocks_send(api, create_task, agent1, claim, django_capture_on_commit_callbacks):
    from support.factories import opportunity_bundle

    create_task("SAAS_OPPORTUNITY_RESEARCH", {"industry": "Dental"})
    s = claim(agent1)
    idea_approval = s.results(opportunity_bundle()).json()["approvals_requested"][0]["approval_id"]
    s.post("complete")
    _decide(api, idea_approval)
    s2 = claim(agent1)
    assert s2.task["task_type"] == "SAAS_CUSTOMER_RESEARCH"
    assert s2.task["context"]["software_idea"]["name"] == "ChairFill"
    rep = s2.results(customer_bundle(legal_basis="UNKNOWN")).json()
    _decide(api, rep["approvals_requested"][0]["approval_id"])
    _launch(api, rep["refs"]["campaigns"]["c1"], django_capture_on_commit_callbacks)
    msg = OutreachMessage.objects.get()
    assert msg.status == "FAILED" and msg.error["reasons"] == ["legal_basis_unknown"]
    assert mail.outbox == []


def test_consent_required_country(api, local_pending, workspace, django_capture_on_commit_callbacks):
    Workspace.objects.filter(pk=workspace.pk).update(consent_required_countries=["BG"])
    approvals, rep = local_pending
    for a in approvals.values():
        _decide(api, a["approval_id"])
    _launch(api, rep["refs"]["campaigns"]["c1"], django_capture_on_commit_callbacks)
    assert OutreachMessage.objects.get().error["reasons"] == ["consent_required"]


def test_daily_send_limit(api, local_pending, workspace, django_capture_on_commit_callbacks):
    Workspace.objects.filter(pk=workspace.pk).update(daily_send_limit=0)
    approvals, rep = local_pending
    for a in approvals.values():
        _decide(api, a["approval_id"])
    _launch(api, rep["refs"]["campaigns"]["c1"], django_capture_on_commit_callbacks)
    assert OutreachMessage.objects.get().status == "APPROVED"  # waits for tomorrow's quota
    assert api.get(f"/api/v1/campaigns/{rep['refs']['campaigns']['c1']}/").json()["status"] == "ACTIVE"


def test_message_edit_rules(api, local_pending):
    _, rep = local_pending
    msg = OutreachMessage.objects.get()
    r = api.patch(f"/api/v1/outreach-messages/{msg.id}/", {"body": "edited"}, format="json")
    assert r.status_code == 409  # campaign is waiting for approval
    assert api.post(f"/api/v1/outreach-messages/{msg.id}/cancel/").json()["status"] == "CANCELLED"
    a = Approval.objects.get(target_type="CAMPAIGN")
    r = api.post(f"/api/v1/approvals/{a.id}/decide/", {"decision": "APPROVED"}, format="json")
    assert r.status_code == 400  # nothing left to approve


def test_lead_never_contacted_twice_if_disqualified(api, local_pending, django_capture_on_commit_callbacks):
    approvals, rep = local_pending
    for a in approvals.values():
        _decide(api, a["approval_id"])
    Lead.objects.update(status="DISQUALIFIED")
    _launch(api, rep["refs"]["campaigns"]["c1"], django_capture_on_commit_callbacks)
    assert OutreachMessage.objects.get().error["reasons"] == ["lead_not_contactable"]
