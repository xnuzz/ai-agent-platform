import pytest

from apps.approvals.models import Approval
from apps.orchestration.models import ResearchTask
from apps.research.models import SoftwareIdea
from support.factories import opportunity_bundle

from .conftest import OPP_INPUT

pytestmark = pytest.mark.django_db


@pytest.fixture
def pending(create_task, agent1, claim):
    create_task("SAAS_OPPORTUNITY_RESEARCH", OPP_INPUT)
    s = claim(agent1)
    rep = s.results(opportunity_bundle()).json()
    s.post("complete")
    return rep["approvals_requested"][0]["approval_id"]


def decide(client, approval_id, decision, **extra):
    return client.post(f"/api/v1/approvals/{approval_id}/decide/", {"decision": decision, **extra}, format="json")


def test_approval_center_lists_pending(api, pending):
    r = api.get("/api/v1/approvals/?status=PENDING").json()
    assert r["count"] == 1 and r["results"][0]["target_type"] == "SOFTWARE_IDEA"


def test_viewer_cannot_decide(viewer_api, pending):
    assert decide(viewer_api, pending, "APPROVED").status_code == 403


def test_agent_has_no_decision_endpoint(agent1, pending):
    assert decide(agent1, pending, "APPROVED").status_code == 401


def test_approve_idea_starts_customer_research(developer_api, pending):
    r = decide(developer_api, pending, "APPROVED", options={"customer_research_input": {"max_leads": 5}})
    assert r.status_code == 200, r.content
    body = r.json()
    task = ResearchTask.objects.get(pk=body["outcome"]["follow_up_task_id"])
    assert task.task_type == "SAAS_CUSTOMER_RESEARCH" and task.input["max_leads"] == 5
    assert task.software_idea.status == "APPROVED" and task.software_idea.approved_by is not None
    assert decide(developer_api, pending, "REJECTED").status_code == 409  # already decided


def test_approve_without_auto_continue(api, pending):
    decide(api, pending, "APPROVED", options={"auto_continue": False})
    assert not ResearchTask.objects.filter(task_type="SAAS_CUSTOMER_RESEARCH").exists()


def test_changes_requested_then_edit_and_resubmit(api, pending):
    idea_id = Approval.objects.get(pk=pending).target_id
    url = f"/api/v1/software-ideas/{idea_id}/"
    assert api.patch(url, {"name": "Too early"}, format="json").status_code == 409  # locked while pending
    decide(api, pending, "CHANGES_REQUESTED", comment="Narrow the ICP")
    assert api.patch(url, {"target_customers": "Clinics with 1-3 chairs"}, format="json").status_code == 200
    r = api.post(f"{url}submit/", {"summary": "Narrowed ICP"}, format="json")
    assert r.status_code == 201 and r.json()["status"] == "PENDING"
    assert api.post(f"{url}submit/", {}, format="json").status_code == 409


def test_stale_content_blocks_decision(api, pending):
    idea_id = Approval.objects.get(pk=pending).target_id
    SoftwareIdea.objects.filter(pk=idea_id).update(summary="tampered outside the API")
    r = decide(api, pending, "APPROVED")
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_approval"


def test_reject(api, pending):
    decide(api, pending, "REJECTED", comment="No")
    assert SoftwareIdea.objects.get().status == "REJECTED"
