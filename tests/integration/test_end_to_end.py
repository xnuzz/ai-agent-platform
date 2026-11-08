"""Cross-component integration test: Vue-equivalent user calls (JWT/HTTP) + agents via platform_sdk (HTTP)
against a live backend. Agent handlers below are MOCK agents emitting fixed bundles — they stand in for
Team 1 / Team 2 implementations and exercise the exact contract those agents must use.
"""
import httpx
import pytest
from django.core import mail

from apps.common.enums import AgentType
from apps.orchestration.models import AgentToken
from platform_sdk import AgentWorker, PlatformClient, TaskContext
from support.factories import customer_bundle, local_leads_bundle, make_user, make_workspace, opportunity_bundle

pytestmark = pytest.mark.django_db(transaction=True)
PASSWORD = "S3cure-pass-123"


class User:
    def __init__(self, base, email, ws_id):
        tok = httpx.post(f"{base}/api/v1/auth/token/", json={"email": email, "password": PASSWORD}).json()
        self.http = httpx.Client(base_url=f"{base}/api/v1/", headers={
            "Authorization": f"Bearer {tok['access']}", "X-Workspace-ID": ws_id})

    def get(self, path, **params):
        r = self.http.get(path, params=params)
        assert r.status_code == 200, r.text
        return r.json()

    def post(self, path, json=None, expect=(200, 201)):
        r = self.http.post(path, json=json or {})
        assert r.status_code in expect, r.text
        return r.json()

    def approve_all_pending(self):
        for a in self.get("approvals/", status="PENDING")["results"]:
            self.post(f"approvals/{a['id']}/decide/", {"decision": "APPROVED"})


def agent_worker(base, agent, handlers):
    _, key = AgentToken.issue(name=f"e2e-{agent}", agent=agent)
    return AgentWorker(PlatformClient(base, key), handlers, worker_id=f"e2e-{agent}", heartbeat_interval=30)


# ---- mock agent handlers (contract-conformant) ----

def mock_opportunity_research(ctx: TaskContext):
    assert ctx.input["industry"] == "Dental clinics"
    ctx.progress(30, stage="SEARCHING", message="mock search")
    rep = ctx.submit(opportunity_bundle())
    ctx.progress(90, stage="FINALIZING")
    return {"ideas": len(rep["refs"]["software_ideas"])}


def mock_customer_research(ctx: TaskContext):
    assert ctx.task.context["software_idea"]["status"] == "APPROVED"
    assert ctx.check_suppression(emails=["info@smile-dental.test"])["suppressed_emails"] == []
    ctx.submit(customer_bundle())
    return {"leads": 1}


def mock_local_discovery(ctx: TaskContext):
    ctx.progress(50, stage="SCANNING_WEBSITES")
    ctx.submit(local_leads_bundle())
    return {"businesses": 1, "briefs": 1}


def test_full_platform_flow(live_server):
    base = live_server.url
    owner = make_user(email="owner@example.com", password=PASSWORD)
    ws = make_workspace(owner)
    user = User(base, "owner@example.com", str(ws.id))
    agent1 = agent_worker(base, AgentType.SAAS_RESEARCH, {
        "SAAS_OPPORTUNITY_RESEARCH": mock_opportunity_research,
        "SAAS_CUSTOMER_RESEARCH": mock_customer_research,
    })
    agent2 = agent_worker(base, AgentType.LOCAL_LEADS, {"LOCAL_LEAD_DISCOVERY": mock_local_discovery})

    # --- Agent 1, phase 1: research -> idea -> WAITING_FOR_APPROVAL
    t1 = user.post("research-tasks/", {"task_type": "SAAS_OPPORTUNITY_RESEARCH",
                                       "input": {"industry": "Dental clinics"}})
    assert agent2.run_once() is False  # agent 2 never sees agent 1 work
    assert agent1.run_once() is True
    t1 = user.get(f"research-tasks/{t1['id']}/")
    assert t1["status"] == "COMPLETED" and t1["result_summary"] == {"ideas": 1}
    assert t1["result_counts"]["evidence"] == 2
    idea = user.get("software-ideas/")["results"][0]
    assert idea["status"] == "WAITING_FOR_APPROVAL"

    # --- Developer approves idea -> backend queues customer research automatically
    user.approve_all_pending()
    assert user.get(f"software-ideas/{idea['id']}/")["status"] == "APPROVED"
    assert agent1.run_once() is True  # phase 2
    campaign = user.get("campaigns/", source="SAAS_RESEARCH")["results"][0]
    assert campaign["status"] == "WAITING_FOR_APPROVAL" and campaign["software_idea"] == idea["id"]

    # --- Outreach is impossible before approval
    r = user.http.post(f"campaigns/{campaign['id']}/launch/")
    assert r.status_code == 409

    user.approve_all_pending()
    user.post(f"campaigns/{campaign['id']}/launch/")
    assert user.get(f"campaigns/{campaign['id']}/")["status"] == "COMPLETED"
    assert [m.to for m in mail.outbox] == [["info@smile-dental.test"]]

    # --- Agent 2: location -> leads + brief + outreach (parallel) -> WAITING_FOR_APPROVAL
    t2 = user.post("research-tasks/", {"task_type": "LOCAL_LEAD_DISCOVERY",
                                       "input": {"location": {"city": "Plovdiv", "country_code": "BG"}}})
    assert agent2.run_once() is True
    assert user.get(f"research-tasks/{t2['id']}/")["status"] == "COMPLETED"
    pending = {a["target_type"] for a in user.get("approvals/", status="PENDING")["results"]}
    assert pending == {"PROJECT_BRIEF", "CAMPAIGN"}
    user.approve_all_pending()
    c2 = user.get("campaigns/", source="LOCAL_LEADS")["results"][0]
    user.post(f"campaigns/{c2['id']}/launch/")
    assert len(mail.outbox) == 2

    # --- Recipient opts out through the link in the email; future outreach is blocked
    link = next(line for line in mail.outbox[1].body.splitlines() if "/unsubscribe/" in line)
    token = link.rsplit("/unsubscribe/", 1)[1].strip()
    assert httpx.post(f"{base}/api/v1/public/unsubscribe/{token}/").status_code == 200
    supp = user.get("suppression-entries/")["results"]
    assert supp[0]["value"] == "hello@bakery.test" and supp[0]["source"] == "UNSUBSCRIBE_LINK"

    # --- Dashboard reflects both agents through one backend
    dash = user.get("dashboard/summary/")
    assert dash["leads_by_source"] == {"SAAS_RESEARCH": 1, "LOCAL_LEADS": 1}
    assert dash["outreach_messages"] == {"SENT": 2}
    actions = {e["action"] for e in user.get("audit-events/", page_size=100)["results"]}
    assert {"approval.approved", "campaign.launched", "outreach_message.sent", "suppression.created"} <= actions


def test_agent_failure_and_cancellation_reported(live_server):
    base = live_server.url
    owner = make_user(email="owner2@example.com", password=PASSWORD)
    ws = make_workspace(owner)
    user = User(base, "owner2@example.com", str(ws.id))

    def boom(ctx):
        raise ValueError("LLM provider returned garbage")

    agent = agent_worker(base, AgentType.SAAS_RESEARCH, {"SAAS_OPPORTUNITY_RESEARCH": boom})
    t = user.post("research-tasks/", {"task_type": "SAAS_OPPORTUNITY_RESEARCH", "input": {"industry": "x"}})
    agent.run_once()
    t = user.get(f"research-tasks/{t['id']}/")
    assert t["status"] == "FAILED" and t["error"]["code"] == "agent_error"

    def cancellable(ctx):
        user.post(f"research-tasks/{ctx.task.id}/cancel/")
        ctx.progress(10)  # raises TaskCancelled

    agent.handlers = {"SAAS_OPPORTUNITY_RESEARCH": cancellable}
    t = user.post("research-tasks/", {"task_type": "SAAS_OPPORTUNITY_RESEARCH", "input": {"industry": "y"}})
    agent.run_once()
    assert user.get(f"research-tasks/{t['id']}/")["status"] == "CANCELLED"
