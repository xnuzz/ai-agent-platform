"""E2E data helper (MOCK agents — fixed bundles from tests/support/bundles.py, no real research).

  python e2e/seed.py workspace   -> registers owner + teammate, creates one task per agent, runs mock agents;
                                    prints JSON {email, password, teammate}
  python e2e/seed.py drain       -> runs mock agents until the queue is empty; prints {"processed": n}

Talks to the API over HTTP like a real client/agent. Agent tokens are issued through the Django ORM
(same as `manage.py create_agent_token`), so DATABASE_URL must point at the e2e database.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "agents" / "platform_sdk"), str(ROOT / "tests")]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
import httpx  # noqa: E402

django.setup()

from apps.common.enums import AgentType  # noqa: E402
from apps.orchestration.models import AgentToken  # noqa: E402
from platform_sdk import AgentWorker, PlatformClient  # noqa: E402
from support.bundles import customer_bundle, local_leads_bundle, opportunity_bundle  # noqa: E402

API = f"http://127.0.0.1:{os.environ.get('E2E_API_PORT', '8000')}"
PASSWORD = "E2e-flow-pass-123"


def workers():
    _, k1 = AgentToken.issue(name="e2e-agent1", agent=AgentType.SAAS_RESEARCH)
    _, k2 = AgentToken.issue(name="e2e-agent2", agent=AgentType.LOCAL_LEADS)
    submit = lambda b: (lambda ctx: (ctx.submit(b), {})[1])  # noqa: E731
    return [
        AgentWorker(PlatformClient(API, k1), {"SAAS_OPPORTUNITY_RESEARCH": submit(opportunity_bundle()),
                                              "SAAS_CUSTOMER_RESEARCH": submit(customer_bundle())}),
        AgentWorker(PlatformClient(API, k2), {"LOCAL_LEAD_DISCOVERY": submit(local_leads_bundle())}),
    ]


def drain() -> int:
    n, ws = 0, workers()
    while any([w.run_once() for w in ws]):
        n += 1
    return n


def register(email):
    httpx.post(f"{API}/api/v1/auth/register/", json={"email": email, "password": PASSWORD,
                                                      "workspace_name": f"E2E {email}"}).raise_for_status()


def workspace() -> dict:
    stamp = f"{int(time.time() * 1000)}"
    email, teammate = f"e2e{stamp}@example.com", f"e2e-mate{stamp}@example.com"
    register(email)
    register(teammate)
    tok = httpx.post(f"{API}/api/v1/auth/token/", json={"email": email, "password": PASSWORD}).json()["access"]
    ws = httpx.get(f"{API}/api/v1/workspaces/", headers={"Authorization": f"Bearer {tok}"}).json()["results"][0]["id"]
    c = httpx.Client(base_url=f"{API}/api/v1/", headers={"Authorization": f"Bearer {tok}", "X-Workspace-ID": ws})
    c.post("research-tasks/", json={"task_type": "SAAS_OPPORTUNITY_RESEARCH",
                                    "input": {"industry": "Dental"}}).raise_for_status()
    c.post("research-tasks/", json={"task_type": "LOCAL_LEAD_DISCOVERY",
                                    "input": {"location": {"city": "Plovdiv", "country_code": "BG"}}}).raise_for_status()
    drain()
    return {"email": email, "password": PASSWORD, "teammate": teammate}


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "workspace"
    print(json.dumps({"processed": drain()} if mode == "drain" else workspace()))
