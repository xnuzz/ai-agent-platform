"""🧪 MOCK LLM provider — deterministic, offline, for tests and local development ONLY.

It does not call any model. It reads the structured `<input>` block each pipeline step embeds in its prompt and
returns canned-but-consistent output (every text is prefixed "MOCK"), always citing ids that exist in the input so
the full pipeline + backend contract can be exercised end-to-end. Override any step with `responders`.
Selected with LLM_PROVIDER=fake; the CLI refuses to run it unless AGENT1_ALLOW_MOCK_PROVIDERS=true.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from ..errors import LLMOutputError
from ..schemas import (BusinessAssessment, BusinessAssessments, CompetitorMention, CustomerSearchPlan,
                       DimensionRatings, IdeaDraft, IdeaDrafts, MessageDraft, MessageDrafts, OfferDraft,
                       OpportunityRating, OpportunityRatings, ProblemCandidate, ProblemExtraction, SearchQuery)
from ..sources.fake import is_mock_business_url
from .base import T, extract_input

Responder = Callable[[dict], BaseModel]


def _problems(data: dict) -> ProblemExtraction:
    sources = [s for s in data.get("sources", []) if not is_mock_business_url(s.get("url", ""))]
    reviews = [s for s in sources if s.get("type") == "REVIEW"]
    n = min(int(data.get("max_problems") or 3), max(1, len(sources) // 2))
    out = []
    for k in range(n):
        cited = [s["id"] for s in sources[2 * k: 2 * k + 2]] or [sources[0]["id"]] if sources else []
        comps = [CompetitorMention(name="MockSuite", source_id=reviews[0]["id"], notes="MOCK: too expensive")] \
            if reviews else []
        out.append(ProblemCandidate(
            title=f"MOCK problem {k + 1}: manual {data.get('industry', 'industry')} workflow",
            problem_statement=f"MOCK: businesses in {data.get('industry')} handle this by hand (sources {cited}).",
            target_segment=data.get("customer_segment") or "ANY", pain_severity=5 - (k % 3),
            source_ids=cited, competitors=comps))
    return ProblemExtraction(problems=out)


def _ratings(data: dict) -> OpportunityRatings:
    out = []
    for i, o in enumerate(data.get("opportunities", [])):
        out.append(OpportunityRating(
            opportunity_id=o["opportunity_id"],
            ratings=DimensionRatings(pain=int(o.get("pain_severity") or 3), frequency=4, willingness_to_pay=3 + i % 2,
                                     competition_gap=4 - (1 if i % 3 == 2 else 0), feasibility=4),
            rationale=f"MOCK rationale for {o['opportunity_id']}"))
    return OpportunityRatings(ratings=out)


def _ideas(data: dict) -> IdeaDrafts:
    opps = data.get("opportunities", [])
    out = []
    for i in range(min(int(data.get("max_ideas") or 1), max(len(opps), 1) * 2)):
        if not opps:
            break
        o = opps[i % len(opps)]
        ev = [e["id"] for e in o.get("evidence", [])][:1]
        out.append(IdeaDraft(
            opportunity_id=o["opportunity_id"], name=f"MOCK Idea {i + 1}",
            summary=f"MOCK: software that automates '{o['title']}'.", problem=o["problem_statement"],
            solution="MOCK: a simple web app with automation.", target_customers=f"MOCK {data.get('industry')} SMBs",
            key_features=["MOCK feature A", "MOCK feature B"], pricing_model="MOCK hypothesis: EUR 49/month",
            differentiation="MOCK: cheaper and simpler", risks=["MOCK risk: distribution"],
            mvp_scope="MOCK: 4-week MVP", idea_score=80 - 10 * i, source_ids=ev))
    return IdeaDrafts(ideas=out)


def _plan(data: dict) -> CustomerSearchPlan:
    target = (data.get("idea") or {}).get("target_customers") or (data.get("idea") or {}).get("name", "customers")
    regions = data.get("regions") or [""]
    return CustomerSearchPlan(queries=[SearchQuery(query=f"{target} {r}".strip(), country_code=r) for r in regions])


def _assess(data: dict) -> BusinessAssessments:
    out = []
    for i, s in enumerate(data.get("sources", [])):
        biz = is_mock_business_url(s.get("url", ""))
        name = s.get("title", "").replace("[MOCK] ", "")
        out.append(BusinessAssessment(source_id=s["id"], is_individual_business=biz, business_name=name if biz else "",
                                      category="MOCK category" if biz else "", city="Mocktown" if biz else "",
                                      fit_score=(85 - (i % 3) * 10) if biz else 0,
                                      fit_rationale="MOCK: matches target customers" if biz else ""))
    return BusinessAssessments(assessments=out)


def _offer(data: dict) -> OfferDraft:
    name = (data.get("idea") or {}).get("name", "the product")
    return OfferDraft(headline=f"MOCK offer: {name}", value_proposition=f"MOCK: {name} saves hours every week.",
                      pricing="MOCK pilot: first month free", call_to_action="MOCK: 15-minute call next week?")


def _messages(data: dict) -> MessageDrafts:
    out = []
    for lead in data.get("leads", []):
        out.append(MessageDraft(
            lead_id=lead["lead_id"], subject=f"MOCK: an idea for {lead['business_name']}",
            body=(f"Hello {lead['business_name']} team,\n\nMOCK DRAFT: we built a tool for businesses like yours "
                  f"in {lead.get('city') or 'your area'}.\n\nWould a 15-minute call next week be useful?\n\n"
                  f"Best regards,\nMock Sender")))
    return MessageDrafts(messages=out)


DEFAULT_RESPONDERS: dict[type[BaseModel], Responder] = {
    ProblemExtraction: _problems, OpportunityRatings: _ratings, IdeaDrafts: _ideas, CustomerSearchPlan: _plan,
    BusinessAssessments: _assess, OfferDraft: _offer, MessageDrafts: _messages,
}


class FakeLLMProvider:
    """🧪 Mock LLM. `responders` override per output model: {OutputModel: fn(input_dict) -> instance}."""

    name = "fake"

    def __init__(self, model: str = "fake-deterministic", responders: dict[type[BaseModel], Responder] | None = None):
        self.model = model
        self.responders = {**DEFAULT_RESPONDERS, **(responders or {})}
        self.calls: list[dict[str, Any]] = []

    def generate(self, *, system: str, prompt: str, output_model: type[T], max_tokens: int | None = None) -> T:
        data = extract_input(prompt)
        self.calls.append({"output_model": output_model.__name__, "input": data, "system": system})
        fn = self.responders.get(output_model)
        if fn is None:
            raise LLMOutputError(f"FakeLLMProvider has no responder for {output_model.__name__}")
        return output_model.model_validate(fn(data).model_dump())
