from datetime import timedelta

import pytest
from django.utils import timezone

from apps.common.enums import MessageStatus, Role
from apps.orchestration.models import AgentToken, ResearchTask
from apps.outreach.models import Campaign, OutreachMessage
from support.bundles import local_leads_bundle
from support.factories import add_member

from .conftest import LOCAL_INPUT, _client

pytestmark = pytest.mark.django_db
URL = "/api/v1/dashboard/operations/"


def agent(ops, name):
    return next(a for a in ops["agents"] if a["agent"] == name)


def test_operations_reflect_real_task_state(api, create_task, agent2, claim):
    ops = api.get(URL).json()
    a2 = agent(ops, "LOCAL_LEADS")
    assert a2["state"] in ("IDLE", "OFFLINE") and a2["queued"] == 0 and a2["current_tasks"] == []

    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    s = claim(agent2)                                    # claiming also marks the worker as seen
    s.results(local_leads_bundle())
    a2 = agent(api.get(URL).json(), "LOCAL_LEADS")
    assert a2["state"] == "RUNNING" and a2["worker_last_seen_at"]
    assert a2["current_tasks"][0]["attempt"] == 1 and a2["leads"] == 1 and a2["businesses"] == 1

    ResearchTask.objects.update(lease_expires_at=timezone.now() - timedelta(minutes=1))
    ops = api.get(URL).json()
    assert agent(ops, "LOCAL_LEADS")["state"] == "STALLED" and agent(ops, "LOCAL_LEADS")["stuck"] == 1
    assert ops["alerts"][0]["code"] == "task_stalled" and ops["alerts"][0]["level"] == "critical"

    s.post("complete")
    a2 = agent(api.get(URL).json(), "LOCAL_LEADS")
    assert a2["state"] == "IDLE" and a2["last_success_at"] and a2["qualified_leads"] == 1


def test_offline_worker_and_failures_raise_alerts(api, create_task, agent2, claim):
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    claim(agent2).post("fail", {"code": "agent_error", "message": "Overpass 504", "retryable": False})
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    ResearchTask.objects.filter(status="QUEUED").update(created_at=timezone.now() - timedelta(hours=1))
    AgentToken.objects.update(last_used_at=timezone.now() - timedelta(hours=1))
    ops = api.get(URL).json()
    a2 = agent(ops, "LOCAL_LEADS")
    assert a2["state"] == "OFFLINE" and a2["failed_24h"] == 1
    assert a2["recent_errors"][0]["message"] == "Overpass 504"
    assert {"worker_offline", "tasks_failed"} <= {x["code"] for x in ops["alerts"]}


def test_other_workspaces_are_invisible(api, create_task, agent2, claim, owner):
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    claim(agent2).results(local_leads_bundle())
    from support.factories import make_workspace

    other = _client(owner, make_workspace(owner, name="Other"))
    a2 = agent(other.get(URL).json(), "LOCAL_LEADS")
    assert a2["current_tasks"] == [] and a2["leads"] == 0


def test_stuck_sending_alert_and_admin_resolution(api, workspace, create_task, agent2, claim):
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    claim(agent2).results(local_leads_bundle())
    Campaign.objects.update(status="ACTIVE")
    OutreachMessage.objects.update(status=MessageStatus.SENDING)
    OutreachMessage.objects.update(updated_at=timezone.now() - timedelta(hours=1))
    ops = api.get(URL).json()
    assert ops["messages_stuck_sending"] == 1 and ops["alerts"][0]["code"] == "messages_stuck_sending"

    msg = OutreachMessage.objects.get()
    dev = _client(add_member(workspace, "dev2@example.com", Role.DEVELOPER), workspace)
    url = f"/api/v1/outreach-messages/{msg.id}/resolve-sending/"
    assert dev.post(url, {"outcome": "SENT"}, format="json").status_code == 403
    r = api.post(url, {"outcome": "FAILED", "note": "bounced at provider"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "FAILED"
    assert api.post(url, {"outcome": "SENT"}, format="json").status_code == 409   # already resolved
    assert api.get(URL).json()["messages_stuck_sending"] == 0


def test_resolving_as_sent_marks_lead_contacted(api, create_task, agent2, claim):
    create_task("LOCAL_LEAD_DISCOVERY", LOCAL_INPUT)
    claim(agent2).results(local_leads_bundle())
    OutreachMessage.objects.update(status=MessageStatus.SENDING)
    msg = OutreachMessage.objects.get()
    r = api.post(f"/api/v1/outreach-messages/{msg.id}/resolve-sending/", {"outcome": "SENT"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "SENT"
    msg.refresh_from_db()
    assert msg.sent_at and msg.lead.status == "CONTACTED"
