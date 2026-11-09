"""Handler + bundle builder against local websites, fake discovery and fake LLM, with an in-memory context.

Every submitted bundle is validated with the backend's own ResultBundle serializer (contract conformance)
and every ref is checked to resolve within the task, as the backend's ingestion requires.
"""
import pytest
from a2_helpers import FakeContext, good_site_routes, poor_site_routes
from apps.orchestration.bundle import ResultBundle
from local_leads import LocalLeadsAgent
from local_leads.config import CrawlerSettings, Settings
from local_leads.discovery import DiscoveryUnavailable
from local_leads.discovery.fake import FakeDiscoveryProvider
from local_leads.llm.fake import FakeLLMProvider
from platform_sdk import RetryableError

STAGES = ["PLANNING", "DISCOVERING_BUSINESSES", "SCANNING_WEBSITES", "QUALIFYING", "WRITING_BRIEFS",
          "DRAFTING_OUTREACH", "SUBMITTING"]


def settings(**kw) -> Settings:
    return Settings(llm_provider="fake", discovery_provider="fake", batch_size=kw.pop("batch_size", 10),
                    crawler=CrawlerSettings(info_url="https://bot-info.test", min_host_interval=0.0,
                                            connect_timeout=2, read_timeout=3, trust_env=False), **kw)


def businesses(poor, good, suppressed):
    return [
        {"provider_id": "poor", "name": "Corner Bakery", "category": "Bakery", "website": poor.url,
         "phone": "+359 32 111", "latitude": 42.123456789, "longitude": 24.7},
        {"provider_id": "good", "name": "Modern Dental Studio", "category": "Dentist", "website": good.url,
         "email": "dr.ivanov@moderndental.test"},
        {"provider_id": "nosite", "name": "Old Town Locksmith", "category": "Locksmith", "website": "",
         "phone": "+359 32 222"},
        {"provider_id": "supp", "name": "Quiet Florist", "category": "Florist", "website": suppressed.url,
         "email": "info@quietflorist.test"},
        {"provider_id": "badurl", "name": "Broken Listing", "category": "Bakery", "website": "not a url at all",
         "email": "info@broken.test"},
    ]


def run(sites, task_input, *, batch_size=10, llm=None, suppressed=()):
    poor = sites(poor_site_routes(), host="127.0.0.2")
    good = sites(good_site_routes(), host="127.0.0.3")
    supp = sites(poor_site_routes(), host="127.0.0.11")
    agent = LocalLeadsAgent(settings(batch_size=batch_size),
                            discovery=FakeDiscoveryProvider(businesses(poor, good, supp)),
                            llm=llm if llm is not None else FakeLLMProvider())
    ctx = FakeContext(task_input, suppressed_emails=suppressed)
    summary = agent(ctx)
    agent.close()
    return ctx, summary


def assert_bundles_conform(bundles):
    refs = {k: set() for k in ("evidence", "businesses", "leads", "project_briefs", "campaigns")}
    for bundle in bundles:
        ser = ResultBundle(data=bundle)
        assert ser.is_valid(), ser.errors
        assert set(bundle) <= {"schema_version", "evidence", "businesses", "leads", "project_briefs", "campaigns"}
        for section in refs:
            for item in bundle.get(section, []):
                assert len(item["ref"]) <= 200 and item["ref"] not in refs[section]
                refs[section].add(item["ref"])
        ev = refs["evidence"]
        for b in bundle.get("businesses", []):
            assert b["evidence_refs"] and set(b["evidence_refs"]) <= ev
        for lead in bundle.get("leads", []):
            assert lead["business_ref"] in refs["businesses"] and set(lead["evidence_refs"]) <= ev
            for p in lead["problems"]:
                assert p["evidence_refs"] and set(p["evidence_refs"]) <= ev, p
        for pb in bundle.get("project_briefs", []):
            assert pb["lead_ref"] in refs["leads"] and set(pb["evidence_refs"]) <= ev
        for c in bundle.get("campaigns", []):
            assert c["project_brief_ref"] in refs["project_briefs"] and c["submit_for_approval"] is True
            assert all(m["sequence_step"] == 1 and m["lead_ref"] in refs["leads"] for m in c["messages"])
    return refs


def merged(bundles, section):
    return [item for b in bundles for item in b.get(section, [])]


def test_full_run_conforms_and_qualifies(sites):
    ctx, summary = run(sites, {"location": {"city": "Plovdiv", "country_code": "BG"}, "min_score": 50},
                       batch_size=2, suppressed={"info@quietflorist.test"})
    assert len(ctx.bundles) == 3                                   # 5 businesses in batches of 2
    assert_bundles_conform(ctx.bundles)
    stages = [s for _, s, _ in ctx.progress_calls]
    assert [s for s in dict.fromkeys(stages)] == STAGES
    assert [p for p, _, _ in ctx.progress_calls] == sorted(p for p, _, _ in ctx.progress_calls)

    leads = {lead["ref"]: lead for lead in merged(ctx.bundles, "leads")}
    biz = {b["ref"]: b for b in merged(ctx.bundles, "businesses")}
    by_name = {biz[lead["business_ref"]]["name"]: lead for lead in leads.values()}
    assert len(by_name) == 5
    poor, good = by_name["Corner Bakery"], by_name["Modern Dental Studio"]
    assert poor["status"] == "QUALIFIED" and poor["score"] >= 50
    assert poor["contact"]["email"] == "info@cornerbakery.test"           # found on the website
    assert poor["contact"]["email_type"] == "GENERIC_BUSINESS" and poor["contact"]["legal_basis"] == \
        "LEGITIMATE_INTEREST"
    assert good["status"] == "DISQUALIFIED" and {p["code"] for p in good["problems"]} == {"NO_HTTPS"}
    assert good["contact"]["email"] == "office@moderndental.test"          # personal listing e-mail dropped
    nosite = by_name["Old Town Locksmith"]
    assert [p["code"] for p in nosite["problems"]] == ["NO_WEBSITE"] and nosite["status"] == "QUALIFIED"
    assert "no usable e-mail" in nosite["qualification_notes"]
    assert by_name["Broken Listing"]["problems"] == []                      # invalid URL: not scanned
    assert biz[by_name["Broken Listing"]["business_ref"]]["website"] == ""
    assert biz[poor["business_ref"]]["latitude"] == 42.123457                # rounded to 6 dp

    briefs = {pb["lead_ref"]: pb for pb in merged(ctx.bundles, "project_briefs")}
    campaigns = {c["messages"][0]["lead_ref"]: c for c in merged(ctx.bundles, "campaigns")}
    qualified = {r for r, lead in leads.items() if lead["status"] == "QUALIFIED"}
    assert set(briefs) == qualified                                          # one brief per qualified lead
    pb = briefs[poor["ref"]]
    assert pb["submit_for_approval"] is True and pb["estimated_budget"]["currency"] == "EUR"
    assert pb["estimated_effort_hours"]["min"] <= pb["estimated_effort_hours"]["max"]
    assert pb["scope_items"] and pb["tech_stack"] and pb["problems"] == poor["problems"]
    assert "fake:mock" in pb["approval_summary"]
    # outreach: only poor (nosite has no e-mail; florist is suppressed)
    assert set(campaigns) == {poor["ref"]}
    msg = campaigns[poor["ref"]]["messages"][0]
    assert campaigns[poor["ref"]]["project_brief_ref"] == pb["ref"]
    assert msg["language"] == "en" and "unsubscribe" not in msg["body"].lower()
    florist = by_name["Quiet Florist"]
    assert florist["status"] == "QUALIFIED" and briefs[florist["ref"]]["submit_for_approval"] is False
    assert "suppression list" in briefs[florist["ref"]]["approval_summary"]
    assert briefs[nosite["ref"]]["submit_for_approval"] is True

    # suppression was checked before drafting, per batch, for the qualified contacts
    assert ["info@cornerbakery.test"] in [c[0] for c in ctx.suppression_calls]
    assert all(call[2] == i for i, call in enumerate(ctx.suppression_calls[:1]))
    assert summary["businesses_found"] == 5 and summary["campaigns"] == 1 and summary["briefs"] == 3
    assert summary["qualified"] == 3 and summary["disqualified"] == 2 and summary["suppressed_contacts"] == 1
    assert summary["approvals_requested"] == 3 and summary["llm_provider"] == "fake:mock"


def test_checks_and_min_score_are_respected(sites):
    ctx, summary = run(sites, {"location": {"city": "Plovdiv", "country_code": "BG"}, "checks": ["NO_HTTPS", "BOGUS"],
                               "min_score": 0, "categories": ["Bakery"]})
    assert_bundles_conform(ctx.bundles)
    leads = merged(ctx.bundles, "leads")
    assert len(leads) == 2                                               # categories filter (fake provider)
    assert {p["code"] for lead in leads for p in lead["problems"]} <= {"NO_HTTPS"}
    assert all(lead["status"] == "QUALIFIED" for lead in leads)          # min_score 0 qualifies everyone
    assert summary["unknown_checks"] == ["BOGUS"] and summary["checks"] == ["NO_HTTPS"]


def test_template_fallback_when_llm_fails(sites):
    from local_leads.llm import LLMUnavailable

    llm = FakeLLMProvider(scripted={"project_brief": [LLMUnavailable("down")] * 10,
                                    "outreach_email": [LLMUnavailable("down")] * 10})
    ctx, summary = run(sites, {"location": {"city": "Plovdiv", "country_code": "BG"}, "language": "de"}, llm=llm)
    assert_bundles_conform(ctx.bundles)
    assert summary["template_written"] >= 2 and summary["llm_written"] == 0
    msg = merged(ctx.bundles, "campaigns")[0]["messages"][0]
    assert msg["language"] == "en"                                       # honest: template text is English
    assert "Text by template" in merged(ctx.bundles, "project_briefs")[0]["approval_summary"]


def test_discovery_outage_is_retryable():
    class Down(FakeDiscoveryProvider):
        def discover(self, inp, *, limit):
            raise DiscoveryUnavailable("HTTP 503")

    agent = LocalLeadsAgent(settings(), discovery=Down([]), llm=None)
    with pytest.raises(RetryableError):
        agent(FakeContext({"location": {"city": "X", "country_code": "BG"}}))
