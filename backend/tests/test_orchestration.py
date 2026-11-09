from datetime import timedelta

import pytest
from django.utils import timezone

from apps.orchestration.models import ResearchTask
from apps.orchestration.services import reap_expired_leases

from .conftest import LOCAL_INPUT, OPP_INPUT

pytestmark = pytest.mark.django_db


def test_create_task_validates_input(api):
    r = api.post("/api/v1/research-tasks/", {"task_type": "LOCAL_LEAD_DISCOVERY", "input": {"location": {}}},
                 format="json")
    assert r.status_code == 400
    assert "input" in r.json()["error"]["details"]


def test_customer_research_requires_approved_idea(api, create_task):
    r = api.post("/api/v1/research-tasks/", {"task_type": "SAAS_CUSTOMER_RESEARCH",
                                             "input": {"software_idea_id": "00000000-0000-0000-0000-000000000000"}},
                 format="json")
    assert r.status_code == 400


def test_task_routed_to_correct_agent(create_task, agent1, agent2, claim):
    t = create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    assert t["agent"] == "LOCAL_LEADS" and t["status"] == "QUEUED"
    assert t["input"]["location"]["radius_km"] == 10  # defaults applied
    assert claim(agent1) is None
    s = claim(agent2)
    assert s.task["id"] == t["id"] and s.task["attempt"] == 1


def test_heartbeat_progress_and_lease_enforcement(create_task, agent1, claim, api):
    t = create_task("SAAS_OPPORTUNITY_RESEARCH", OPP_INPUT)
    s = claim(agent1)
    r = s.post("heartbeat", {"progress": 40, "stage": "SEARCHING", "message": "Reading forums"})
    assert r.status_code == 200 and r.json()["cancel_requested"] is False
    detail = api.get(f"/api/v1/research-tasks/{t['id']}/").json()
    assert detail["progress"] == 40 and detail["stage"] == "SEARCHING"

    bad = agent1.post(f"/api/v1/agent/tasks/{t['id']}/heartbeat/", {}, format="json",
                      HTTP_X_LEASE_ID="11111111-1111-1111-1111-111111111111")
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "lease_lost"


def test_agent_cannot_touch_other_agents_task(create_task, agent1, agent2, claim):
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    s = claim(agent2)
    r = agent1.post(f"/api/v1/agent/tasks/{s.task['id']}/complete/", {}, format="json",
                    HTTP_X_LEASE_ID=s.task["lease_id"])
    assert r.status_code == 404


def test_auth_separation(api, agent1):
    assert agent1.get("/api/v1/research-tasks/").status_code == 401
    assert api.post("/api/v1/agent/tasks/claim/", {"worker_id": "x"}, format="json").status_code in (401, 403)


def test_cancel_running_task(create_task, agent1, claim, api):
    t = create_task("SAAS_OPPORTUNITY_RESEARCH", OPP_INPUT)
    s = claim(agent1)
    assert api.post(f"/api/v1/research-tasks/{t['id']}/cancel/").json()["cancel_requested"] is True
    assert s.post("heartbeat", {}).json()["cancel_requested"] is True
    assert s.results({"schema_version": "1.0"}).json()["error"]["code"] == "cancel_requested"
    assert s.post("fail", {"code": "CANCELLED"}).json()["status"] == "CANCELLED"


def test_cancel_queued_task(create_task, api):
    t = create_task("SAAS_OPPORTUNITY_RESEARCH", OPP_INPUT)
    assert api.post(f"/api/v1/research-tasks/{t['id']}/cancel/").json()["status"] == "CANCELLED"
    assert api.post(f"/api/v1/research-tasks/{t['id']}/cancel/").status_code == 409


def test_retryable_failure_requeues_then_fails(create_task, agent1, claim, api):
    t = create_task("SAAS_OPPORTUNITY_RESEARCH", OPP_INPUT)
    for attempt in (1, 2):
        s = claim(agent1)
        assert s.task["attempt"] == attempt
        assert s.post("fail", {"code": "rate_limited", "retryable": True}).json()["status"] == "QUEUED"
    s = claim(agent1)
    assert s.post("fail", {"code": "rate_limited", "retryable": True}).json()["status"] == "FAILED"
    assert api.post(f"/api/v1/research-tasks/{t['id']}/retry/").json()["status"] == "QUEUED"


def test_expired_lease_is_reaped(create_task, agent1, claim):
    t = create_task("SAAS_OPPORTUNITY_RESEARCH", OPP_INPUT)
    s = claim(agent1)
    ResearchTask.objects.filter(pk=t["id"]).update(lease_expires_at=timezone.now() - timedelta(seconds=1))
    assert reap_expired_leases() == 1
    assert ResearchTask.objects.get(pk=t["id"]).status == "QUEUED"
    assert s.post("heartbeat", {}).status_code == 409  # old worker lost the lease
    assert claim(agent1).task["attempt"] == 2


def test_complete_sets_summary(create_task, agent1, claim, api):
    t = create_task("SAAS_OPPORTUNITY_RESEARCH", OPP_INPUT)
    s = claim(agent1)
    assert s.post("complete", {"summary": {"ideas": 0}}).json()["status"] == "COMPLETED"
    d = api.get(f"/api/v1/research-tasks/{t['id']}/").json()
    assert d["result_summary"] == {"ideas": 0} and d["progress"] == 100
