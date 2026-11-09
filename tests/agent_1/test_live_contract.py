"""Live contract test: Agent 1's REAL handlers (with 🧪 mock LLM/search/fetch providers) against the REAL backend
over HTTP via platform_sdk — task created -> worker claims -> bundles accepted -> approval -> customer research ->
campaign pending -> (human) approve + launch -> only lawful recipients are emailed.

Pattern: tests/integration/test_end_to_end.py.
"""
import httpx
import pytest
from django.core import mail

from apps.common.enums import AgentType
from apps.orchestration.models import AgentToken
from platform_sdk import AgentWorker, PlatformClient
from saas_research.handlers import Agent1Handlers, PipelineOptions, Providers
from saas_research.llm.fake_provider import FakeLLMProvider
from saas_research.sources.fake import FakePageFetcher, FakeSearchProvider
from support.factories import make_user, make_workspace

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


def agent1_worker(base):
    _, key = AgentToken.issue(name="a1-contract", agent=AgentType.SAAS_RESEARCH)
    handlers = Agent1Handlers(Providers(FakeLLMProvider(), FakeSearchProvider(), FakePageFetcher()),
                              PipelineOptions(batch_size=3))
    return AgentWorker(PlatformClient(base, key), handlers.as_dict(), worker_id="a1-contract",
                       heartbeat_interval=30)


def test_agent1_real_handlers_against_live_backend(live_server):
    base = live_server.url
    owner = make_user(email="a1owner@example.com", password=PASSWORD)
    ws = make_workspace(owner)
    user = User(base, "a1owner@example.com", str(ws.id))
    worker = agent1_worker(base)

    # --- phase 1: opportunity research
    t1 = user.post("research-tasks/", {"task_type": "SAAS_OPPORTUNITY_RESEARCH", "input": {
        "industry": "Dental clinics", "regions": ["BG"], "keywords": ["no-shows"], "max_opportunities": 2,
        "max_ideas": 2}})
    assert worker.run_once() is True
    t1 = user.get(f"research-tasks/{t1['id']}/")
    assert t1["status"] == "COMPLETED", t1
    assert t1["result_summary"]["opportunities"] == 2 and t1["result_summary"]["ideas"] == 2
    assert t1["result_counts"]["opportunities"] == 2 and t1["result_counts"]["software_ideas"] == 2

    evidence = user.get("evidence/", page_size=100)["results"]
    assert evidence and all(e["url"].startswith("https://") and e["retrieved_at"] for e in evidence)
    opps = user.get("opportunities/")["results"]
    assert all(o["evidence_ids"] and o["score"] is not None for o in opps)
    ideas = user.get("software-ideas/")["results"]
    waiting = [i for i in ideas if i["status"] == "WAITING_FOR_APPROVAL"]
    assert waiting and all(i["opportunity"] in {o["id"] for o in opps} for i in ideas)
    approvals = user.get("approvals/", status="PENDING")["results"]
    assert {a["target_type"] for a in approvals} == {"SOFTWARE_IDEA"}
    assert all(a["summary"].startswith(("Recommendation", "LOW CONFIDENCE")) for a in approvals)

    # --- human approves the best idea -> backend queues customer research with our options
    best = max(waiting, key=lambda i: i["score"])
    appr = next(a for a in approvals if a["target_id"] == best["id"])
    decided = user.post(f"approvals/{appr['id']}/decide/", {
        "decision": "APPROVED", "options": {"customer_research_input": {"max_leads": 4, "regions": ["BG"]}}})
    follow_up = decided["outcome"]["follow_up_task_id"]

    # --- phase 2: customer research (real handler reads task.context.software_idea)
    assert worker.run_once() is True
    t2 = user.get(f"research-tasks/{follow_up}/")
    assert t2["status"] == "COMPLETED", t2
    summary = t2["result_summary"]
    leads = user.get("leads/", source="SAAS_RESEARCH")["results"]
    assert 1 <= len(leads) <= 4 and summary["leads"] == len(leads)
    campaign = user.get("campaigns/", source="SAAS_RESEARCH")["results"][0]
    assert campaign["status"] == "WAITING_FOR_APPROVAL" and campaign["software_idea"] == best["id"]
    msgs = user.get("outreach-messages/", campaign=campaign["id"], page_size=100)["results"]
    assert len(msgs) == summary["messages"] == len(leads)
    assert all(m["status"] == "WAITING_FOR_APPROVAL" and m["sequence_step"] == 1 for m in msgs)
    assert mail.outbox == []  # the agent never sends

    # --- launch is blocked before approval; after approval only LEGITIMATE_INTEREST leads are emailed
    assert user.http.post(f"campaigns/{campaign['id']}/launch/").status_code == 409
    camp_appr = next(a for a in user.get("approvals/", status="PENDING")["results"]
                     if a["target_type"] == "CAMPAIGN")
    user.post(f"approvals/{camp_appr['id']}/decide/", {"decision": "APPROVED"})
    user.post(f"campaigns/{campaign['id']}/launch/")
    lawful = sorted(lead_["contact_email"] for lead_ in leads if lead_["legal_basis"] == "LEGITIMATE_INTEREST")
    assert lawful and sorted(m.to[0] for m in mail.outbox) == lawful
    assert summary["legal_basis_unknown"] == len(leads) - len(lawful)
