"""Deterministic pieces: input defaults, contact choice, scoring, project estimates, settings."""
import pytest
from local_leads.briefs import build_estimate
from local_leads.config import DEFAULT_LLM_MODEL, Settings
from local_leads.contacts import choose_contact, classify_email
from local_leads.models import Finding, TaskInput
from local_leads.problems import ALL_CODES, PROBLEMS, spec
from local_leads.scoring import NEED_CAP, score_lead


def finding(code):
    s = spec(code)
    return Finding(code=code, severity=s.severity, title=s.title, description=f"{code} measured")


def test_task_input_defaults_and_normalisation():
    inp = TaskInput.parse({"location": {"city": " Plovdiv ", "country_code": "bg"}})
    assert (inp.location.city, inp.location.country_code, inp.location.radius_km) == ("Plovdiv", "BG", 10)
    assert (inp.categories, inp.max_businesses, inp.checks, inp.min_score, inp.language) == ([], 25, [], 50, "en")
    inp = TaskInput.parse({"location": {"city": "A", "country_code": "DE", "radius_km": 500}, "min_score": 0,
                           "max_businesses": 999, "checks": ["no_https"]})
    assert inp.location.radius_km == 100 and inp.min_score == 0 and inp.max_businesses == 200
    assert inp.checks == ["NO_HTTPS"]
    with pytest.raises(ValueError):
        TaskInput.parse({"location": {"city": "A"}})


def test_problem_catalog_matches_contract_vocabulary():
    contract = {"NO_WEBSITE", "NO_HTTPS", "SSL_EXPIRED", "SLOW_PAGE_LOAD", "NOT_MOBILE_FRIENDLY", "BROKEN_LINKS",
                "OUTDATED_CMS", "OUTDATED_DESIGN", "NO_ONLINE_BOOKING", "NO_CONTACT_FORM", "POOR_SEO", "MISSING_META",
                "ACCESSIBILITY_ISSUES", "NO_ANALYTICS", "SECURITY_HEADERS_MISSING", "NO_GOOGLE_BUSINESS_PROFILE"}
    added = {"WEBSITE_UNREACHABLE", "NO_HTTPS_REDIRECT", "SSL_INVALID_CERTIFICATE", "SSL_EXPIRING_SOON",
             "MIXED_CONTENT"}
    assert ALL_CODES == contract | added
    assert all(s.severity in ("LOW", "MEDIUM", "HIGH") and s.weight > 0 for s in PROBLEMS.values())


@pytest.mark.parametrize("email,kind", [
    ("info@bakery.test", "GENERIC_BUSINESS"), ("Office2@bakery.test", "GENERIC_BUSINESS"),
    ("cornerbakery@gmail.test", "GENERIC_BUSINESS"), ("john.smith@bakery.test", "PERSONAL_WORK"),
    ("j.smith@bakery.test", "PERSONAL_WORK"), ("xq7@bakery.test", "UNKNOWN"), ("noreply@bakery.test", "EXCLUDED"),
    ("not-an-email", "EXCLUDED"),
])
def test_classify_email(email, kind):
    assert classify_email(email, "Corner Bakery") == kind


def test_choose_contact_prefers_generic_on_site_and_drops_personal():
    c = choose_contact([("anna.berg@bakery.test", "listing"), ("hello@other.test", "listing"),
                        ("info@bakery.test", "website")], business_name="X", website="https://www.bakery.test",
                       country_code="DE")
    assert (c.email, c.email_type, c.legal_basis) == ("info@bakery.test", "GENERIC_BUSINESS", "LEGITIMATE_INTEREST")
    assert "DE" in c.legal_basis_note and "not legal advice" in c.legal_basis_note
    c = choose_contact([("xq7@bakery.test", "website")], business_name="X")
    assert (c.email_type, c.legal_basis) == ("UNKNOWN", "UNKNOWN")
    assert choose_contact([("anna.berg@bakery.test", "website")], business_name="X") is None


def test_scoring_is_deterministic_and_explained():
    contact = choose_contact([("info@a.test", "w")], business_name="A")
    a = score_lead([finding("NO_HTTPS"), finding("NOT_MOBILE_FRIENDLY"), finding("NO_HTTPS")], contact, min_score=50)
    assert a.score == 30 + 25 + 10 and a.status == "QUALIFIED"
    assert a.breakdown == [("NO_HTTPS", 30), ("NOT_MOBILE_FRIENDLY", 25), ("contact: generic_business e-mail", 10)]
    assert "NO_HTTPS +30" in a.notes and "threshold 50" in a.notes
    assert score_lead([finding("NO_HTTPS")], contact, min_score=41).status == "DISQUALIFIED"
    assert score_lead([finding("NO_HTTPS")], contact, min_score=40).status == "QUALIFIED"   # >= threshold
    every = [finding(c) for c in ALL_CODES]
    assert score_lead(every, contact, min_score=50).score == NEED_CAP + 10
    assert score_lead([finding("NO_WEBSITE")], None, min_score=50).score == 50   # 60 - 10 (no e-mail)
    assert score_lead([], None, min_score=0).score == 0


def test_estimates():
    est = build_estimate([finding("NO_HTTPS"), finding("MISSING_META")], hourly_rate=50, currency="eur")
    assert est.approach == "fixes" and est.currency == "EUR"
    assert est.scope_items[-1].startswith("Project management")
    assert (est.hours_min, est.hours_max) == (2 + 2 + 2, 4 + 4 + 2)
    assert (est.budget_min, est.budget_max) == (300.0, 500.0)
    est = build_estimate([finding("NOT_MOBILE_FRIENDLY"), finding("OUTDATED_CMS"), finding("NO_CONTACT_FORM")],
                         hourly_rate=60)
    assert est.approach == "rebuild" and est.scope_items[0].startswith("Rebuild")
    assert any("contact form" in s for s in est.scope_items)            # not covered by rebuild
    assert not any("Responsive" in s for s in est.scope_items)          # covered by rebuild
    assert build_estimate([finding("NO_WEBSITE")], hourly_rate=60).approach == "new_site"
    assert build_estimate([finding("WEBSITE_UNREACHABLE")], hourly_rate=60).approach == "relaunch"
    est = build_estimate([finding("OUTDATED_CMS")], hourly_rate=60, cms="WordPress")
    assert "WordPress (current supported version)" in est.tech_stack


def test_settings_from_env():
    s = Settings.from_env({})
    assert s.llm_provider == "anthropic" and s.llm_model == DEFAULT_LLM_MODEL == "claude-sonnet-5-5"
    assert s.discovery_provider == "google_places" and s.batch_size == 10 and s.crawler.min_host_interval == 1.0
    s = Settings.from_env({"LLM_MODEL": "", "BATCH_SIZE": "3", "CRAWLER_INFO_URL": "https://me.test/bot",
                           "LLM_SERVER_FALLBACK": "false", "BRIEF_CURRENCY": "usd"})
    assert s.llm_model == DEFAULT_LLM_MODEL and s.batch_size == 3 and s.currency == "USD"
    assert s.llm_server_fallback is False and s.crawler.user_agent == "LocalLeadsBot/0.1 (+https://me.test/bot)"
