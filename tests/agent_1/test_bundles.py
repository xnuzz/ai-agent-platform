"""Bundle builder + local validator, cross-checked against the backend's own ResultBundle serializer.

`apps.orchestration.bundle.ResultBundle` is the backend's contract definition; importing it in a test (never in the
agent itself) gives a precise, DB-free conformance check of every bundle the agent produces.
"""
import copy

import pytest

from agent_1.fakes import FakeCtx
from apps.orchestration.bundle import ResultBundle
from saas_research.handlers import Agent1Handlers, Providers
from saas_research.llm.fake_provider import FakeLLMProvider
from saas_research.pipeline.bundles import BatchSubmitter, BundleValidationError, chunked, validate_bundle
from saas_research.sources.fake import FakePageFetcher, FakeSearchProvider
from support.bundles import customer_bundle, opportunity_bundle

IDEA = {"id": "11111111-1111-1111-1111-111111111111", "name": "ChairFill", "status": "APPROVED",
        "target_customers": "small dental clinics"}


def handlers():
    return Agent1Handlers(Providers(FakeLLMProvider(), FakeSearchProvider(), FakePageFetcher()))


def run_opportunity(**inp):
    ctx = FakeCtx("SAAS_OPPORTUNITY_RESEARCH", {"industry": "Dental clinics", **inp})
    handlers().opportunity_research(ctx)
    return ctx


def run_customer(**inp):
    ctx = FakeCtx("SAAS_CUSTOMER_RESEARCH", {"software_idea_id": IDEA["id"], **inp}, {"software_idea": IDEA})
    handlers().customer_research(ctx)
    return ctx


def assert_backend_accepts(bundle):
    ser = ResultBundle(data=bundle)
    assert ser.is_valid(), ser.errors


@pytest.mark.parametrize("run", [run_opportunity, run_customer])
def test_every_submitted_bundle_passes_backend_serializer(run):
    ctx = run(regions=["BG"])
    assert ctx.bundles
    for b in ctx.bundles:
        assert_backend_accepts(b)


def test_opportunity_bundles_follow_agent1_contract():
    ctx = run_opportunity(max_opportunities=2, max_ideas=2)
    evidence = {e["ref"]: e for e in ctx.section("evidence")}
    opps, ideas = ctx.section("opportunities"), ctx.section("software_ideas")
    assert 1 <= len(opps) <= 2 and 1 <= len(ideas) <= 2
    assert not any(ctx.section(s) for s in ("businesses", "leads", "campaigns", "project_briefs"))
    # evidence is submitted before (or with) the items that cite it, and every citation resolves
    first_use = {}
    for i, b in enumerate(ctx.bundles):
        for e in b["evidence"]:
            first_use.setdefault(e["ref"], i)
        for it in b["opportunities"] + b["software_ideas"]:
            assert it["evidence_refs"] and all(first_use.get(r, 99) <= i for r in it["evidence_refs"])
    for e in evidence.values():
        assert e["url"].startswith("https://") and e["retrieved_at"] and e["excerpt"] and e["source_type"]
    for o in opps:
        assert all(set(c) == {"name", "url", "notes"} for c in o["competitors"])
    opp_refs = {o["ref"] for o in opps}
    assert all(i["opportunity_ref"] in opp_refs for i in ideas)
    assert any(i["submit_for_approval"] and i["approval_summary"] for i in ideas)


def test_customer_bundles_follow_agent1_contract():
    ctx = run_customer(max_leads=4, regions=["BG"])
    leads, msgs = ctx.section("leads"), [m for c in ctx.section("campaigns") for m in c["messages"]]
    assert not any(ctx.section(s) for s in ("opportunities", "software_ideas", "project_briefs"))
    assert 1 <= len(leads) <= 4 and len(ctx.section("campaigns")) == 1
    biz_refs = {b["ref"] for b in ctx.section("businesses")}
    assert all(lead["business_ref"] in biz_refs for lead in leads)
    for lead in leads:
        c = lead["contact"]
        assert c["email"] and c["legal_basis"] in {"LEGITIMATE_INTEREST", "UNKNOWN"}
        assert (c["legal_basis"] == "LEGITIMATE_INTEREST") == (c["email_type"] == "GENERIC_BUSINESS")
    camp = ctx.section("campaigns")[0]
    assert camp["channel"] == "EMAIL" and camp["submit_for_approval"] and camp["approval_summary"]
    assert set(camp["offer"]) == {"headline", "value_proposition", "pricing", "call_to_action"}
    for m in msgs:
        assert m["sequence_step"] == 1 and m["language"] == "en"
        low = m["body"].lower()
        assert "unsubscribe" not in low and "regards" not in low and "mock sender" not in low


def test_reference_bundles_pass_local_validator():
    validate_bundle(opportunity_bundle(), "SAAS_OPPORTUNITY_RESEARCH")
    validate_bundle(customer_bundle(), "SAAS_CUSTOMER_RESEARCH")


@pytest.mark.parametrize("mutate,match", [
    (lambda b: b.update(schema_version="2.0"), "schema_version"),
    (lambda b: b.update(businesses=[{"ref": "b1", "name": "x"}]), "not allowed"),
    (lambda b: b["opportunities"][0].update(evidence_refs=["nope"]), "unknown ref"),
    (lambda b: b["opportunities"][0].update(evidence_refs=[]), "at least one evidence"),
    (lambda b: b["software_ideas"][0].update(opportunity_ref="op404"), "unknown ref"),
    (lambda b: b["evidence"].append(dict(b["evidence"][0])), "duplicate refs"),
    (lambda b: b["evidence"][0].update(url="ftp://x"), "http"),
    (lambda b: b["opportunities"][0].update(pain_severity=9), "1..5"),
])
def test_local_validator_rejects_opportunity_contract_violations(mutate, match):
    b = copy.deepcopy(opportunity_bundle())
    mutate(b)
    with pytest.raises(BundleValidationError, match=match):
        validate_bundle(b, "SAAS_OPPORTUNITY_RESEARCH")


@pytest.mark.parametrize("mutate,match", [
    (lambda b: b["campaigns"][0]["messages"][0].update(sequence_step=2), "sequence_step"),
    (lambda b: b["campaigns"][0]["messages"][0].update(lead_ref="l404"), "unknown ref"),
    (lambda b: b["campaigns"][0].update(project_brief_ref="pb1"), "LOCAL_LEAD_DISCOVERY"),
    (lambda b: b["leads"][0]["contact"].update(legal_basis="MAYBE"), "legal_basis"),
    (lambda b: b["leads"][0].update(business_id="x"), "exactly one"),
])
def test_local_validator_rejects_customer_contract_violations(mutate, match):
    b = copy.deepcopy(customer_bundle())
    mutate(b)
    with pytest.raises(BundleValidationError, match=match):
        validate_bundle(b, "SAAS_CUSTOMER_RESEARCH")


def test_batch_submitter_tracks_refs_across_batches_and_chunks():
    sent = []
    sub = BatchSubmitter(lambda b: sent.append(b) or {"created": {"evidence": len(b["evidence"])}},
                         "SAAS_OPPORTUNITY_RESEARCH", batch_size=1)
    ob = opportunity_bundle()
    sub.send_batched("opportunities", ob["opportunities"], evidence=ob["evidence"])
    assert [len(b["evidence"]) for b in sent] == [1, 1, 0] and sub.created == {"evidence": 2}
    sub.send(software_ideas=ob["software_ideas"])  # refs from earlier batches resolve
    with pytest.raises(BundleValidationError):
        sub.send(software_ideas=[{**ob["software_ideas"][0], "ref": "i2", "opportunity_ref": "zzz"}])
    assert sub.send(evidence=[]) is None and sub.calls == 4
    assert chunked([1, 2, 3], 2) == [[1, 2], [3]] and chunked([], 5) == [[]]
