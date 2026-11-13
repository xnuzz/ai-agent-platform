"""Live contract test: the REAL Agent 2 handler (fake discovery 🧪 + fake LLM 🧪, real website analyzer against
local test sites) runs through platform_sdk against a live backend (pytest-django `live_server`).

task created -> worker claims -> bundles accepted -> brief + campaign approvals pending -> launch blocked until
BOTH are approved -> launch -> backend sends with its footer. Pattern: tests/integration/test_end_to_end.py.
"""
import httpx
import pytest
from a2_helpers import good_site_routes, poor_site_routes
from apps.common.enums import AgentType
from apps.orchestration.models import AgentToken
from django.core import mail
from local_leads import LocalLeadsAgent, build_worker
from local_leads.config import CrawlerSettings, Settings
from local_leads.discovery.fake import FakeDiscoveryProvider
from local_leads.llm.fake import FakeLLMProvider
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


def test_agent2_end_to_end_against_live_backend(live_server, sites):
    base = live_server.url
    owner = make_user(email="a2-owner@example.com", password=PASSWORD)
    ws = make_workspace(owner)
    user = User(base, "a2-owner@example.com", str(ws.id))

    poor = sites(poor_site_routes(), host="127.0.0.2")
    good = sites(good_site_routes(), host="127.0.0.3")
    florist = sites(poor_site_routes(), host="127.0.0.11")
    discovery = FakeDiscoveryProvider([
        {"provider_id": "poor", "name": "Corner Bakery", "category": "Bakery", "website": poor.url,
         "phone": "+359 32 111 111", "address_line1": "5 Main St", "postal_code": "4000"},
        {"provider_id": "good", "name": "Modern Dental Studio", "category": "Dentist", "website": good.url},
        {"provider_id": "nosite", "name": "Old Town Locksmith", "category": "Locksmith", "phone": "+359 32 222"},
        {"provider_id": "florist", "name": "Quiet Florist", "category": "Florist", "website": florist.url},
    ])
    # the florist opted out earlier -> agent must not draft outreach to it
    user.post("suppression-entries/", {"type": "EMAIL", "value": "info@quietflorist.test", "reason": "OPT_OUT"})
    florist.routes["/"].body = florist.routes["/"].body.replace("info@cornerbakery.test", "info@quietflorist.test")

    settings = Settings(find_missing_websites=False, platform_api_url=base, discovery_provider="fake", llm_provider="fake", batch_size=2,
                        poll_interval=0.1, heartbeat_interval=30,
                        crawler=CrawlerSettings(info_url="https://bot-info.test", min_host_interval=0.0,
                                                connect_timeout=2, read_timeout=3, trust_env=False))
    _, key = AgentToken.issue(name="a2-contract", agent=AgentType.LOCAL_LEADS)
    settings.platform_agent_token = key
    agent = LocalLeadsAgent(settings, discovery=discovery, llm=FakeLLMProvider())
    worker = build_worker(settings, agent=agent)

    # --- user creates the task; worker claims and runs the real handler
    task = user.post("research-tasks/", {"task_type": "LOCAL_LEAD_DISCOVERY", "input": {
        "location": {"city": "Plovdiv", "country_code": "bg", "radius_km": 15}, "min_score": 50,
        "language": "en"}})
    assert worker.run_once() is True
    agent.close()
    task = user.get(f"research-tasks/{task['id']}/")
    assert task["status"] == "COMPLETED", task
    summary = task["result_summary"]
    assert summary["businesses_found"] == 4 and summary["batches"] == 2 and summary["campaigns"] == 1
    assert summary["qualified"] == 3 and summary["disqualified"] == 1

    # --- persisted entities
    leads = user.get("leads/", source="LOCAL_LEADS", page_size=100)["results"]
    assert len(leads) == 4 and len(user.get("businesses/", page_size=100)["results"]) == 4
    assert sorted(lead["status"] for lead in leads) == ["DISQUALIFIED", "QUALIFIED", "QUALIFIED", "QUALIFIED"]
    scans = user.get("evidence/", research_task=task["id"], source_type="WEBSITE_SCAN", page_size=100)
    assert scans["count"] >= 3
    briefs = user.get("project-briefs/", research_task=task["id"], page_size=100)["results"]
    assert len(briefs) == 3
    assert sorted(b["status"] for b in briefs) == ["DRAFT", "WAITING_FOR_APPROVAL", "WAITING_FOR_APPROVAL"]

    pending = user.get("approvals/", status="PENDING", page_size=100)["results"]
    assert sorted(a["target_type"] for a in pending) == ["CAMPAIGN", "PROJECT_BRIEF", "PROJECT_BRIEF"]
    campaign = user.get("campaigns/", source="LOCAL_LEADS")["results"]
    assert len(campaign) == 1
    campaign = campaign[0]
    assert campaign["status"] == "WAITING_FOR_APPROVAL" and campaign["project_brief"]
    messages = user.get("outreach-messages/", campaign=campaign["id"])["results"]
    assert [m["to_email"] for m in messages] == ["info@cornerbakery.test"]

    # --- launch is blocked until BOTH brief and campaign are approved
    r = user.http.post(f"campaigns/{campaign['id']}/launch/")
    assert r.status_code == 409
    by_target = {a["target_id"]: a for a in pending}
    user.post(f"approvals/{by_target[campaign['id']]['id']}/decide/", {"decision": "APPROVED"})
    r = user.http.post(f"campaigns/{campaign['id']}/launch/")
    assert r.status_code == 409 and "project_brief_not_approved" in r.text
    user.post(f"approvals/{by_target[campaign['project_brief']]['id']}/decide/", {"decision": "APPROVED"})
    user.post(f"campaigns/{campaign['id']}/launch/")

    # --- backend sent it (agent never sends), with the platform footer appended
    assert user.get(f"campaigns/{campaign['id']}/")["status"] == "COMPLETED"
    assert [m.to for m in mail.outbox] == [["info@cornerbakery.test"]]
    body = mail.outbox[0].body
    assert body.startswith("Hello Corner Bakery team,") and "/unsubscribe/" in body
    assert body.count("/unsubscribe/") == 1   # only the backend's footer
