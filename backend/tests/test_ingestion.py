import pytest

from apps.approvals.models import Approval
from apps.leads.models import Business, Lead
from apps.research.models import Evidence, SoftwareIdea
from support.factories import local_leads_bundle, opportunity_bundle

from .conftest import LOCAL_INPUT, OPP_INPUT

pytestmark = pytest.mark.django_db


@pytest.fixture
def opp_session(create_task, agent1, claim):
    create_task("SAAS_OPPORTUNITY_RESEARCH", OPP_INPUT)
    return claim(agent1)


@pytest.fixture
def local_session(create_task, agent2, claim):
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    return claim(agent2)


def test_opportunity_bundle_persists_and_requests_approval(opp_session):
    r = opp_session.results(opportunity_bundle())
    assert r.status_code == 200, r.content
    rep = r.json()
    assert rep["created"] == {"evidence": 2, "opportunities": 1, "software_ideas": 1}
    idea = SoftwareIdea.objects.get(pk=rep["refs"]["software_ideas"]["idea1"])
    assert idea.status == "WAITING_FOR_APPROVAL" and idea.evidence.count() == 1
    assert idea.opportunity.evidence.count() == 2
    a = Approval.objects.get(pk=rep["approvals_requested"][0]["approval_id"])
    assert a.requested_by_type == "AGENT" and a.requested_by_agent == "SAAS_RESEARCH"
    assert a.snapshot["context"]["evidence"][0]["url"].startswith("https://forum")


def test_resubmission_is_idempotent(opp_session):
    first = opp_session.results(opportunity_bundle()).json()
    second = opp_session.results(opportunity_bundle()).json()
    assert second["created"] == {}
    assert {s["reason"] for s in second["skipped"]} == {"immutable", "not_editable"}
    assert second["refs"]["software_ideas"]["idea1"] == first["refs"]["software_ideas"]["idea1"]
    assert second["approvals_requested"] == []
    assert Approval.objects.count() == 1


def test_unknown_ref_rolls_back_everything(opp_session):
    bundle = opportunity_bundle()
    bundle["software_ideas"][0]["evidence_refs"] = ["nope"]
    r = opp_session.results(bundle)
    assert r.status_code == 400
    assert Evidence.objects.count() == 0 and SoftwareIdea.objects.count() == 0


def test_section_not_allowed_for_task_type(opp_session):
    r = opp_session.results({"schema_version": "1.0", "businesses": [{"ref": "b", "name": "X"}]})
    assert r.status_code == 400 and "businesses" in r.json()["error"]["details"]


def test_schema_version_required(opp_session):
    assert opp_session.results({"evidence": []}).status_code == 400


def test_local_bundle_dedupes_business_across_tasks(local_session, create_task, agent2, claim):
    assert local_session.results(local_leads_bundle(submit=False)).status_code == 200
    local_session.post("complete")
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    s2 = claim(agent2)
    bundle = local_leads_bundle(submit=False)
    bundle["businesses"][0]["website"] = "https://www.BAKERY.test/"  # same domain, different spelling
    rep = s2.results(bundle).json()
    assert Business.objects.count() == 1 and Lead.objects.count() == 1
    assert rep["updated"]["businesses"] == 1


def test_suppressed_recipient_message_skipped(local_session, api):
    api.post("/api/v1/suppression-entries/", {"type": "DOMAIN", "value": "bakery.test", "reason": "MANUAL"},
             format="json")
    rep = local_session.results(local_leads_bundle()).json()
    assert {"kind": "messages", "ref": "c1/l1/1", "reason": "suppressed"} in rep["skipped"]
    assert [a["target_type"] for a in rep["approvals_requested"]] == ["PROJECT_BRIEF"]


def test_agent_suppression_check(local_session, api):
    api.post("/api/v1/suppression-entries/", {"type": "EMAIL", "value": "Hello@Bakery.test"}, format="json")
    r = local_session.client.post("/api/v1/agent/suppression/check/",
                                  {"task_id": local_session.task["id"], "emails": ["hello@bakery.test", "a@b.test"]},
                                  format="json")
    assert r.json()["suppressed_emails"] == ["hello@bakery.test"]
