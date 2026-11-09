"""E2E data helper (MOCK agents — fixed bundles from tests/support/bundles.py, no real research).

  python e2e/seed.py workspace   -> registers owner + teammate, creates one task per agent, runs mock agents;
                                    prints JSON {email, password, teammate}
  python e2e/seed.py drain       -> runs mock agents until the queue is empty; prints {"processed": n}
  python e2e/seed.py empty       -> registers an owner with an empty workspace; prints {email, password, teammate}
  python e2e/seed.py stream      -> MOCK Agent 2: claims one LOCAL_LEAD_DISCOVERY task and submits fixed, fictional
                                    Sofia businesses in 3 delayed batches (live-discovery UI test); prints {"processed": n}

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


def empty() -> dict:
    stamp = f"{int(time.time() * 1000)}"
    email = f"e2e-lbf{stamp}@example.com"
    register(email)
    return {"email": email, "password": PASSWORD, "teammate": ""}


# Fictional businesses at fixed coordinates (Sofia). The 4th has no coordinates: it must stay list-only.
STREAM = [
    [("bella", "E2E Bella Restaurant", "Restaurant", 42.69332, 23.32144, 85, "info@bella.e2e.test",
      [("NO_ONLINE_BOOKING", "No online booking or reservation option", "MEDIUM"),
       ("NOT_MOBILE_FRIENDLY", "Not optimised for mobile devices", "HIGH")])],
    [("vitosha", "E2E Vitosha Dental", "Dentist", 42.68412, 23.31655, 78, "office@vitosha.e2e.test",
      [("OUTDATED_CMS", "Outdated CMS version", "HIGH")]),
     ("studio", "E2E Studio Cut", "Hair salon", 42.69760, 23.33421, 41, "",
      [("MISSING_META", "Missing title or meta description", "LOW")])],
    [("lyulin", "E2E Lyulin Pharmacy", "Pharmacy", None, None, 58, "",
      [("ACCESSIBILITY_ISSUES", "Accessibility issues", "MEDIUM")])],
]


def stream_bundle(batch) -> dict:
    b = {"schema_version": "1.0", "evidence": [], "businesses": [], "leads": [], "project_briefs": [], "campaigns": []}
    for key, name, category, lat, lng, score, email, problems in batch:
        site = f"https://{key}.e2e.test/"
        b["evidence"] += [
            {"ref": f"ev:{key}:listing", "url": f"https://listing.e2e.test/{key}", "source_type": "DIRECTORY",
             "title": f"Directory listing: {name}", "excerpt": f"Name: {name}; Category: {category}"},
            {"ref": f"ev:{key}:scan", "url": site, "source_type": "WEBSITE_SCAN", "title": f"Website scan: {site}",
             "excerpt": "Scanned (mock).", "metadata": {"scanned": True, "scanner": "local_leads.analyzer", "facts": {
                 "https": True, "viewport": "", "html_seconds": 1.2, "html_bytes": 51200, "contact_form": True,
                 "online_booking": False, "analytics_detected": False, "title": name, "meta_description": "",
                 "accessibility_issues": ["3 of 5 images have no alt text", "page language not declared (<html lang>)"],
                 "images": 5, "images_missing_alt": 3, "security_headers_missing": ["content-security-policy"],
                 "seo_issues": [], "links": {"checked": 8, "broken": [{"url": f"{site}old-menu", "status": 404, "error": ""}]},
                 "tls": {"checked": True, "valid": True, "days_left": 120}}}},
        ]
        b["businesses"].append({"ref": f"biz:{key}", "name": name, "website": site, "email": email, "category": category,
                                "address": {"line1": "1 Test St", "city": "Sofia", "country_code": "BG"},
                                "latitude": lat, "longitude": lng, "evidence_refs": [f"ev:{key}:listing", f"ev:{key}:scan"]})
        qualified = score >= 50
        b["leads"].append({"ref": f"lead:{key}", "business_ref": f"biz:{key}", "score": score,
                           "status": "QUALIFIED" if qualified else "DISQUALIFIED", "qualification_notes": f"Mock score {score}.",
                           "problems": [{"code": c, "title": t, "severity": sev, "description": f"{t} (mock finding).",
                                         "evidence_refs": [f"ev:{key}:scan"]} for c, t, sev in problems],
                           "contact": {"email": email, "email_type": "GENERIC_BUSINESS" if email else "UNKNOWN",
                                       "legal_basis": "LEGITIMATE_INTEREST" if email else "UNKNOWN"},
                           "evidence_refs": [f"ev:{key}:scan"]})
        if not qualified:
            continue
        b["project_briefs"].append({"ref": f"brief:{key}", "lead_ref": f"lead:{key}", "title": f"Website project for {name}",
                                    "summary": "Mock brief.", "proposed_solution": "Responsive rebuild with online booking.",
                                    "scope_items": ["Responsive layout", "Booking widget"], "tech_stack": ["Static site"],
                                    "estimated_effort_hours": {"min": 20, "max": 40},
                                    "estimated_budget": {"min": 1000, "max": 2000, "currency": "EUR"},
                                    "evidence_refs": [f"ev:{key}:scan"], "submit_for_approval": True})
        if email:
            b["campaigns"].append({"ref": f"camp:{key}", "name": f"Website project offer - {name}", "project_brief_ref": f"brief:{key}",
                                   "offer": {"headline": f"Website project for {name}", "value_proposition": "Mock.",
                                             "pricing": "EUR 1,000-2,000", "call_to_action": "Short call"},
                                   "messages": [{"lead_ref": f"lead:{key}", "subject": f"An idea for {name}", "body": "Hello, ... (mock)"}],
                                   "submit_for_approval": True})
    return {k: v for k, v in b.items() if v or k == "schema_version"}


def stream(delay: float = 2.0) -> int:
    _, key = AgentToken.issue(name="e2e-agent2-stream", agent=AgentType.LOCAL_LEADS)

    def handler(ctx):
        ctx.progress(5, stage="DISCOVERING_BUSINESSES", message="Searching (mock) for businesses in Sofia, BG")
        time.sleep(delay)
        for n, batch in enumerate(STREAM):
            ctx.progress(10 + n * 30, stage="SCANNING_WEBSITES", message=f"Scanning batch {n + 1} of {len(STREAM)}")
            ctx.submit(stream_bundle(batch))
            time.sleep(delay)
        ctx.progress(100, stage="SUBMITTING", message="Done")
        return {"businesses_found": sum(map(len, STREAM))}

    worker = AgentWorker(PlatformClient(API, key), {"LOCAL_LEAD_DISCOVERY": handler})
    deadline = time.time() + 40
    while time.time() < deadline:
        if worker.run_once():
            return 1
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "workspace"
    out = {"drain": lambda: {"processed": drain()}, "empty": empty, "stream": lambda: {"processed": stream()}}.get(mode, workspace)()
    print(json.dumps(out))
