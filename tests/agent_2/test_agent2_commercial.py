"""Shadow commercial score (local_leads/commercial.py): calculations + ranking on the labelled eval set."""
import json
from itertools import product
from pathlib import Path

from local_leads.briefs import build_estimate
from local_leads.commercial import assess
from local_leads.contacts import ContactChoice
from local_leads.models import DiscoveredBusiness, Finding
from local_leads.problems import spec
from local_leads.scoring import score_lead

CASES = json.loads((Path(__file__).parent / "data" / "commercial_eval.json").read_text(encoding="utf-8"))["cases"]
RANK = {"A": 3, "B": 2, "C": 1}


def finding(code):
    s = spec(code)
    return Finding(code=code, severity=s.severity, title=s.title, description=f"{code} measured")


def build(case, cost_rate=0.0):
    sd = {"provider": case["provider"]}
    for key in ("business_status", "website_search"):
        if case.get(key):
            sd[key] = case[key]
    if case.get("opening_hours"):
        sd["opening_hours"] = True
    if case.get("website_found"):
        sd["website_found"] = {"method": case["website_found"]}
    b = DiscoveredBusiness(provider=case["provider"], provider_id=case["id"], name=case["id"], country_code="BG",
                           phone="+359 88 123 4567" if case["phone"] else "",
                           address_line1="ul. Test 1" if case["address"] else "", source_data=sd)
    contact = (ContactChoice(email="info@x.test", email_type=case["email"], legal_basis="LEGITIMATE_INTEREST",
                             legal_basis_note="", source="listing") if case["email"] else None)
    findings = [finding(c) for c in case["codes"]]
    est = build_estimate(findings, hourly_rate=25, currency="EUR")
    shadow = assess(b, findings, contact, est, scanned=case["scanned"], cost_hourly_rate=cost_rate,
                    website_searched=case.get("website_search") == "not_found",
                    company_info_found=case.get("company_info", False))
    prod = score_lead(findings, contact, min_score=50, has_phone=case["phone"])
    return shadow, prod


def pairwise_accuracy(scores: dict[str, int]) -> float:
    pairs = [(a, b) for a, b in product(CASES, CASES) if RANK[a["label"]] > RANK[b["label"]]]
    return sum(scores[a["id"]] > scores[b["id"]] for a, b in pairs) / len(pairs)


def test_eval_set_ranking_beats_production():
    results = {c["id"]: build(c) for c in CASES}
    shadow = {k: s.score for k, (s, _) in results.items()}
    prod = {k: p.score for k, (_, p) in results.items()}
    by = lambda lab: [shadow[c["id"]] for c in CASES if c["label"] == lab]  # noqa: E731
    assert min(by("A")) > max(by("C")), shadow            # never rank a skip above a pursue
    acc_shadow, acc_prod = pairwise_accuracy(shadow), pairwise_accuracy(prod)
    print(f"\npairwise ranking accuracy: shadow {acc_shadow:.2f}, production {acc_prod:.2f}")
    assert acc_shadow >= 0.9 and acc_shadow >= acc_prod


def test_components_are_explained_and_sum_to_raw():
    shadow, _ = build(CASES[0])
    d = shadow.as_dict()
    assert d["shadow"] is True and d["version"] == "commercial-v1"
    assert {c["name"] for c in d["components"]} == {"need", "value", "contact", "legitimacy"}
    assert all(c["reason"] for c in d["components"]) and 0 <= d["score"] <= 100
    raw = sum(c["points"] for c in d["components"])
    assert d["score"] == round(raw * (0.6 + 0.4 * d["data_confidence"]))


def test_revenue_is_not_profit_and_profit_needs_a_cost_rate():
    case = next(c for c in CASES if c["id"] == "A-rebuild-reachable")
    shadow, _ = build(case)
    est = shadow.estimates
    assert est["revenue"]["min"] > 0 and est["dev_cost"] is None and est["profit"] is None
    assert "profit n/a" in shadow.summary()
    shadow, _ = build(case, cost_rate=15)
    est = shadow.estimates
    h = est["hours"]
    assert est["dev_cost"] == {"min": h["min"] * 15, "max": h["max"] * 15, "currency": "EUR",
                               "basis": "hours x configured cost rate 15/h"}
    assert est["profit"]["min"] == est["revenue"]["min"] - est["dev_cost"]["max"]   # conservative band
    assert est["profit"]["max"] == est["revenue"]["max"] - est["dev_cost"]["min"]


def test_absence_claims_are_low_confidence_and_closed_business_is_capped():
    osm, _ = build(next(c for c in CASES if c["id"] == "B-no-site-osm-phone-only"))
    google, _ = build(next(c for c in CASES if c["id"] == "A-no-site-google-reachable"))
    assert osm.finding_confidence["NO_WEBSITE"] < google.finding_confidence["NO_WEBSITE"] < 0.9
    closed, prod = build(next(c for c in CASES if c["id"] == "C-closed-google"))
    assert closed.score == 5 and closed.components[-1].name == "closed_gate"
    assert prod.score >= 50  # production ranking misses this: the reason to keep shadowing
