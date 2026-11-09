"""Customer research steps: request, query planning, assessment, contacts, legal basis, offer, outreach drafts."""
import pytest

from saas_research.errors import InvalidTaskInput
from saas_research.evidence import EvidenceRegistry
from saas_research.llm.fake_provider import FakeLLMProvider
from saas_research.pipeline.customers import (Candidate, CustomerRequest, assess_candidates, classify_email,
                                              domains_match, find_contacts, legal_basis_for, pick_email,
                                              plan_customer_queries, search_candidates)
from saas_research.pipeline.outreach import draft_messages, draft_offer, sanitize_body
from saas_research.schemas import (BusinessAssessment, BusinessAssessments, CustomerSearchPlan, MessageDraft,
                                   MessageDrafts, SearchQuery)
from saas_research.sources.base import Page, SearchResult
from saas_research.sources.fake import FakePageFetcher, FakeSearchProvider

IDEA = {"id": "11111111-1111-1111-1111-111111111111", "name": "ChairFill", "status": "APPROVED",
        "summary": "Waitlist that fills cancelled slots", "target_customers": "small dental clinics"}


def req(**inp):
    return CustomerRequest.from_task({"software_idea_id": IDEA["id"], **inp}, {"software_idea": IDEA})


def test_request_defaults_and_context_checks():
    r = req()
    assert (r.regions, r.max_leads, r.channels, r.language, r.notes) == ((), 25, ("EMAIL",), "en", "")
    assert r.idea_view()["name"] == "ChairFill" and "status" not in r.idea_view()
    assert req(max_leads=500, regions=["bg"]).max_leads == 200
    with pytest.raises(InvalidTaskInput):
        CustomerRequest.from_task({}, {})
    with pytest.raises(InvalidTaskInput):
        CustomerRequest.from_task({}, {"software_idea": {**IDEA, "status": "REJECTED"}})
    with pytest.raises(InvalidTaskInput):
        CustomerRequest.from_task({"software_idea_id": "other"}, {"software_idea": IDEA})


def test_query_plan_sanitised_to_requested_regions():
    llm = FakeLLMProvider(responders={CustomerSearchPlan: lambda d: CustomerSearchPlan(queries=[
        SearchQuery(query="dental clinic Sofia", country_code="bg"),
        SearchQuery(query="dental clinic Paris", country_code="FR"),  # not requested -> reassigned
        SearchQuery(query="  ", country_code="BG"),
        SearchQuery(query="dental clinic Sofia", country_code="BG"),  # duplicate
    ])})
    qs = plan_customer_queries(llm, req(regions=["BG", "DE"]), max_queries=5)
    assert all(q.country in {"BG", "DE"} for q in qs) and {q.country for q in qs} == {"BG", "DE"}
    assert len([q for q in qs if q.query == "dental clinic Sofia"]) == 1
    glob = plan_customer_queries(FakeLLMProvider(responders={CustomerSearchPlan: lambda d: CustomerSearchPlan(
        queries=[])}), req(), max_queries=3)
    assert glob and all(q.country is None for q in glob)


def _records(registry, urls_titles):
    search = type("S", (), {"name": "t", "search": lambda self, q, **kw: [
        SearchResult(url=u, title=t, snippet=s, retrieved_at="2026-11-09T00:00:00Z", provider="t",
                     country_code="BG") for u, t, s in urls_titles]})()
    from saas_research.pipeline.research import PlannedQuery
    return search_candidates(search, [PlannedQuery("q", "BG")], registry, results_per_query=10, language="en")


def test_assessment_filters_and_grounds_fields():
    reg = EvidenceRegistry()
    recs = _records(reg, [("https://smile.test/", "Smile Dental | Sofia", "Family dental clinic in Sofia"),
                          ("https://smile.test/team", "dup domain", "x"),
                          ("https://top10.test/", "Top 10 dentists", "list"),
                          ("https://weak.test/", "Weak Fit Clinic", "Varna")])
    assert len(recs) == 3  # one per domain

    def assess(d):
        return BusinessAssessments(assessments=[
            BusinessAssessment(source_id="S1", is_individual_business=True, business_name="Smile Dental",
                               category="Dentist", city="Atlantis", fit_score=90, fit_rationale="fits"),
            BusinessAssessment(source_id="S3", is_individual_business=False, fit_score=95),
            BusinessAssessment(source_id="S4", is_individual_business=True, business_name="Weak Fit Clinic",
                               fit_score=10),
            BusinessAssessment(source_id="S42", is_individual_business=True, business_name="Ghost", fit_score=99),
        ])

    cands = assess_candidates(FakeLLMProvider(responders={BusinessAssessments: assess}), req(), recs, min_fit=50)
    assert len(cands) == 1
    c = cands[0]
    assert (c.name, c.city, c.website, c.country_code, c.category) == \
        ("Smile Dental", "", "https://smile.test/", "BG", "Dentist")  # Atlantis not in source -> dropped


def test_email_classification_and_domain_rules():
    assert classify_email("info@x.com") == "GENERIC_BUSINESS"
    assert classify_email("jane.doe@x.com") == "PERSONAL_WORK"
    assert classify_email("jd@x.com") == "UNKNOWN"
    assert domains_match("shop.acme.com", "acme.com") and domains_match("acme.com", "www.acme.com")
    assert not domains_match("acme.com.evil.test", "acme.com") and not domains_match("gmail.com", "acme.com")
    emails = ("jane.doe@acme.com", "info@acme.com", "noreply@acme.com", "info@wix.com", "jd@acme.com")
    assert pick_email(emails, "acme.com") == ("info@acme.com", "GENERIC_BUSINESS")
    assert pick_email(("jane.doe@acme.com", "jd@acme.com"), "acme.com") == ("jd@acme.com", "UNKNOWN")
    assert pick_email(("info@wix.com",), "acme.com") is None


def _cand(email_type, email="info@a.test"):
    from saas_research.evidence import EvidenceRecord
    src = EvidenceRecord("S1", "ev-1", "https://a.test/", "A", "WEB_PAGE", "x", "2026-11-09T00:00:00Z")
    return Candidate(ref="biz-1", name="A", website="https://a.test/", category="", city="", country_code="",
                     fit_score=80, fit_rationale="", source=src, email=email, email_type=email_type)


def test_legal_basis_is_honest():
    basis, note = legal_basis_for(_cand("GENERIC_BUSINESS"))
    assert basis == "LEGITIMATE_INTEREST" and "Generic business address" in note
    for t in ("PERSONAL_WORK", "UNKNOWN"):
        basis, note = legal_basis_for(_cand(t, "jane.doe@a.test"))
        assert basis == "UNKNOWN" and "human" in note


def test_find_contacts_uses_only_own_domain_addresses_and_stops_at_max():
    reg = EvidenceRegistry()
    search, fetcher = FakeSearchProvider(businesses_per_query=8), FakePageFetcher()
    from saas_research.pipeline.research import PlannedQuery
    recs = search_candidates(search, [PlannedQuery("dentist", "BG")], reg, results_per_query=10, language="en")
    cands = assess_candidates(FakeLLMProvider(), req(), recs, min_fit=0)
    found = find_contacts(fetcher, cands, reg, max_leads=3)
    assert len(found) == 3
    for c in found:
        assert c.email.endswith("@" + c.domain) and "webbuilder" not in c.email
        assert c.contact_evidence is not None and c.email in c.contact_evidence.excerpt
    all_found = find_contacts(FakePageFetcher(), cands, EvidenceRegistry(), max_leads=50)
    assert len(all_found) < len(cands)  # some mock sites expose no address on their own domain


def test_find_contacts_ignores_redirects_off_domain():
    class Redirecting:
        name = "t"

        def fetch(self, url):
            return Page(url="https://other.test/", status=200, title="", text="info@other.test",
                        retrieved_at="2026-11-09T00:00:00Z", emails=("info@other.test",))

    assert find_contacts(Redirecting(), [_cand("UNKNOWN", "")], EvidenceRegistry(), max_leads=5) == []


def test_sanitize_body():
    body = ("Hi Smile Dental,\r\n\r\nWe help clinics fill slots.\nUnsubscribe here: http://x\n\n\n"
            "Would a call help?\n\nBest regards,\n[Your Name]\nAcme")
    assert sanitize_body(body) == "Hi Smile Dental,\n\nWe help clinics fill slots.\n\nWould a call help?"
    assert sanitize_body("Thanks for your time — is this relevant?") == "Thanks for your time — is this relevant?"
    assert sanitize_body("Hallo,\nText.\nMit freundlichen Grüßen\nMax") == "Hallo,\nText."


def test_offer_and_messages_batching_language_and_ids():
    leads = []
    for i in range(12):
        c = _cand("GENERIC_BUSINESS", f"info@a{i}.test")
        c.ref, c.name = f"biz-{i}", f"Biz {i}"
        leads.append(c)
    calls = []

    def msgs(d):
        calls.append(d)
        ids = [lead["lead_id"] for lead in d["leads"]]
        out = [MessageDraft(lead_id=i, subject=f"S {i}", body=f"Hello {i}\n\nCheers,\nBob") for i in ids]
        out.append(MessageDraft(lead_id="L999", subject="x", body="y"))  # unknown id ignored
        out.append(MessageDraft(lead_id=ids[0], subject="dup", body="dup"))  # duplicate ignored
        return MessageDrafts(messages=out)

    llm = FakeLLMProvider(responders={MessageDrafts: msgs})
    r = req(language="de")
    offer = draft_offer(llm, r)
    drafts = draft_messages(llm, r, offer, leads, batch_size=5)
    assert len(calls) == 3 and all(c["language"] == "de" for c in calls)
    assert len(drafts) == 12 and {d.lead_ref for d in drafts} == {c.lead_ref for c in leads}
    assert all(d.language == "de" and "Cheers" not in d.body and "Bob" not in d.body for d in drafts)
    assert calls[0]["offer"]["headline"] == offer.headline
