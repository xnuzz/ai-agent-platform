"""Opportunity research steps: query planning, source gathering, extraction, scoring, ideas."""
import pytest

from saas_research.errors import InvalidTaskInput
from saas_research.evidence import EvidenceRegistry, evidence_ref
from saas_research.llm.base import extract_input, render_input
from saas_research.llm.fake_provider import FakeLLMProvider
from saas_research.pipeline.ideas import generate_ideas, mark_recommendations
from saas_research.pipeline.research import ResearchRequest, extract_problems, gather_sources, plan_queries
from saas_research.pipeline.scoring import WEIGHTS, compute_score, score_opportunities
from saas_research.schemas import (CompetitorMention, DimensionRatings, IdeaDraft, IdeaDrafts, OpportunityRating,
                                   OpportunityRatings, ProblemCandidate, ProblemExtraction)
from saas_research.sources.base import SearchResult
from saas_research.sources.fake import FakeSearchProvider


def sr(url, title="t", snippet="s", provider="test"):
    return SearchResult(url=url, title=title, snippet=snippet, retrieved_at="2026-11-09T00:00:00Z", provider=provider)


def registry_with(n=4):
    reg = EvidenceRegistry()
    for i in range(n):
        reg.add_search_result(sr(f"https://forum{i}.example.com/t/{i}", f"Thread {i}", f"pain {i}"))
    return reg


# ---------------------------------------------------------------- request + planning
def test_request_defaults_and_validation():
    r = ResearchRequest.from_input({"industry": "  Dental  clinics "})
    assert (r.industry, r.regions, r.keywords, r.customer_segment, r.max_opportunities, r.max_ideas, r.language,
            r.notes) == ("Dental clinics", (), (), "ANY", 5, 3, "en", "")
    r = ResearchRequest.from_input({"industry": "x", "max_opportunities": 99, "max_ideas": 0, "regions": ["bg"],
                                    "customer_segment": "smb"})
    assert (r.max_opportunities, r.max_ideas, r.regions, r.customer_segment) == (20, 3, ("BG",), "SMB")
    with pytest.raises(InvalidTaskInput):
        ResearchRequest.from_input({"industry": " "})


def test_plan_queries_respects_keywords_regions_segment():
    r = ResearchRequest.from_input({"industry": "Dental clinics", "keywords": ["scheduling", "billing"],
                                    "regions": ["BG", "DE", "FR"], "customer_segment": "SMB",
                                    "max_opportunities": 2})
    qs = plan_queries(r)
    texts = " | ".join(q.query for q in qs)
    assert "scheduling" in texts and "billing" in texts and "small business" in texts
    assert {q.country for q in qs} == {"BG", "DE", "FR"}
    assert len({q.query for q in qs}) == len(qs) or len(qs) <= 3
    global_qs = plan_queries(ResearchRequest.from_input({"industry": "x"}))
    assert all(q.country is None for q in global_qs) and 4 <= len(global_qs) <= 12


def test_gather_sources_passes_language_and_country():
    search = FakeSearchProvider(businesses_per_query=0)
    reg = EvidenceRegistry()
    req = ResearchRequest.from_input({"industry": "x", "regions": ["DE"], "language": "de"})
    n = gather_sources(search, plan_queries(req, 2), reg, results_per_query=5, language=req.language)
    assert n == 4 and all(c["country"] == "DE" and c["language"] == "de" for c in search.calls)


# ---------------------------------------------------------------- evidence registry
def test_registry_dedupes_and_resolves_only_known_ids():
    reg = EvidenceRegistry()
    a = reg.add_search_result(sr("https://a.example.com/1", "<b>A</b>", "x" * 2000))
    assert reg.add_search_result(sr("https://a.example.com/1")) is a
    assert reg.add_search_result(sr("not-a-url")) is None
    assert a.sid == "S1" and a.ref == evidence_ref("https://a.example.com/1", "search")
    assert len(a.excerpt) <= 600 and a.title == "A"
    assert reg.resolve(["S1", "S99", "S1", "https://fabricated.example.com"]) == [a]
    assert reg.pending_bundle_items() == []  # nothing cited yet
    reg.cite([a])
    items = reg.pending_bundle_items()
    assert [i["ref"] for i in items] == [a.ref] and items[0]["retrieved_at"] == "2026-11-09T00:00:00Z"
    assert reg.pending_bundle_items() == []  # submitted once only


def test_render_extract_roundtrip():
    assert extract_input("hello\n" + render_input({"b": 1, "a": [1]})) == {"a": [1], "b": 1}


# ---------------------------------------------------------------- extraction
def test_extract_drops_unsupported_claims_and_uncited_competitors():
    reg = registry_with(3)
    llm = FakeLLMProvider(responders={ProblemExtraction: lambda d: ProblemExtraction(problems=[
        ProblemCandidate(title="Real problem", problem_statement="p", pain_severity=4, source_ids=["S1", "S404"],
                         competitors=[CompetitorMention(name="CitedCo", source_id="S2"),
                                      CompetitorMention(name="InventedCo", source_id="")]),
        ProblemCandidate(title="Hallucinated", problem_statement="p", pain_severity=5, source_ids=["S77"]),
        ProblemCandidate(title="real problem", problem_statement="dup", pain_severity=3, source_ids=["S3"]),
    ])})
    req = ResearchRequest.from_input({"industry": "x"})
    problems = extract_problems(llm, req, reg, max_candidates=5)
    assert [p.title for p in problems] == ["Real problem"]
    p = problems[0]
    assert [e.sid for e in p.evidence] == ["S1"]
    assert p.competitors == [{"name": "CitedCo", "url": "https://forum1.example.com/t/1",
                              "notes": "Mentioned in: Thread 1"}]
    sent = llm.calls[0]["input"]
    assert sent["max_problems"] == 5 and [s["id"] for s in sent["sources"]] == ["S1", "S2", "S3"]


def test_extract_with_no_sources_skips_llm():
    llm = FakeLLMProvider()
    assert extract_problems(llm, ResearchRequest.from_input({"industry": "x"}), EvidenceRegistry(),
                            max_candidates=3) == [] and llm.calls == []


# ---------------------------------------------------------------- scoring
def test_compute_score_formula():
    top = DimensionRatings(pain=5, frequency=5, willingness_to_pay=5, competition_gap=5, feasibility=5)
    low = DimensionRatings(pain=1, frequency=1, willingness_to_pay=1, competition_gap=1, feasibility=1)
    assert compute_score(top, 3) == 100 and compute_score(top, 1) == 85 and compute_score(top, 2) == 93
    assert compute_score(low, 5) == 0 and compute_score(top, 0) == 0
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9


def _problems(n, reg):
    llm = FakeLLMProvider(responders={ProblemExtraction: lambda d: ProblemExtraction(problems=[
        ProblemCandidate(title=f"P{i}", problem_statement="p", pain_severity=3, source_ids=[f"S{i + 1}"])
        for i in range(n)])})
    return extract_problems(llm, ResearchRequest.from_input({"industry": "x"}), reg, max_candidates=n)


def test_scoring_ranks_cuts_and_never_invents_missing_scores():
    reg = registry_with(4)
    problems = _problems(4, reg)

    def ratings(d):
        vals = {"O1": 2, "O2": 5, "O3": 4}  # O4 not rated
        return OpportunityRatings(ratings=[OpportunityRating(
            opportunity_id=k, rationale="r", ratings=DimensionRatings(pain=v, frequency=v, willingness_to_pay=v,
                                                                       competition_gap=v, feasibility=v))
            for k, v in vals.items()])

    req = ResearchRequest.from_input({"industry": "x", "max_opportunities": 3})
    scored = score_opportunities(FakeLLMProvider(responders={OpportunityRatings: ratings}), req, problems)
    assert [s.problem.title for s in scored] == ["P1", "P2", "P0"]  # O4 (unrated) ranked last -> cut
    assert scored[0].score == 85 and scored[0].market_signals["ratings"]["pain"] == 5
    req4 = ResearchRequest.from_input({"industry": "x", "max_opportunities": 4})
    unrated = score_opportunities(FakeLLMProvider(responders={OpportunityRatings: ratings}), req4, problems)[-1]
    assert unrated.score is None and unrated.market_signals["rating_missing"] is True
    assert len({s.ref for s in scored}) == len(scored)


# ---------------------------------------------------------------- ideas
def _opps(reg, n=2):
    req = ResearchRequest.from_input({"industry": "x", "max_opportunities": n})
    return score_opportunities(FakeLLMProvider(), req, _problems(n, reg))


def test_ideas_link_opportunities_cite_evidence_and_respect_max():
    reg = registry_with(3)
    opps = _opps(reg)
    oid = opps[0].problem.oid

    def ideas(d):
        return IdeaDrafts(ideas=[
            IdeaDraft(opportunity_id=oid, name="A", summary="s", idea_score=90, source_ids=["S99"]),  # bad cite
            IdeaDraft(opportunity_id="O404", name="Orphan", summary="s", idea_score=99),
            IdeaDraft(opportunity_id=oid, name="a", summary="dup name", idea_score=50),
            IdeaDraft(opportunity_id=oid, name="B", summary="s", idea_score=10,
                      source_ids=[opps[0].problem.evidence[0].sid]),
            IdeaDraft(opportunity_id=oid, name="C", summary="s", idea_score=10),
        ])

    req = ResearchRequest.from_input({"industry": "x", "max_ideas": 2})
    out = generate_ideas(FakeLLMProvider(responders={IdeaDrafts: ideas}), req, opps, reg)
    assert [i.draft.name for i in out] == ["A", "B"]
    a, b = out
    assert a.evidence_inherited and a.evidence == opps[0].problem.evidence
    assert not b.evidence_inherited and a.opportunity is opps[0]
    assert a.score == round(0.6 * opps[0].score + 0.4 * 90)


def test_recommendations_threshold_and_low_confidence():
    reg = registry_with(2)
    opps = _opps(reg, 1)
    oid = opps[0].problem.oid
    req = ResearchRequest.from_input({"industry": "x", "max_ideas": 3})
    llm = FakeLLMProvider(responders={IdeaDrafts: lambda d: IdeaDrafts(ideas=[
        IdeaDraft(opportunity_id=oid, name=n, summary="s", idea_score=s, risks=["r1"]) for n, s in
        (("Hi", 100), ("Lo", 0))])})
    ideas = mark_recommendations(generate_ideas(llm, req, opps, reg), min_score=60)
    hi, lo = ideas
    assert hi.recommended and not lo.recommended and lo.approval_summary == ""
    assert "Risks: r1" in hi.approval_summary and "Evidence:" in hi.approval_summary
    weak = mark_recommendations(generate_ideas(llm, req, opps, reg), min_score=101)
    assert [i.recommended for i in weak] == [True, False] and weak[0].low_confidence
    assert weak[0].approval_summary.startswith("LOW CONFIDENCE")
