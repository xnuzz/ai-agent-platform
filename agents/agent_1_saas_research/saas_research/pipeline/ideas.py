"""Step 3: software idea generation + recommendation (which ideas go to the human approval gate).

idea.score = round(0.6 · opportunity.score + 0.4 · model_confidence)   (model_confidence alone if unscored)
Recommended (submit_for_approval=True): score ≥ min_score; if none qualifies, the single best idea is still
submitted, explicitly labelled LOW CONFIDENCE in its approval_summary so the developer decides.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..evidence import EvidenceRecord, EvidenceRegistry
from ..llm.base import LLMProvider, render_input
from ..schemas import IdeaDraft, IdeaDrafts
from .common import GROUNDING_RULES, squash, stable_ref, truncate
from .research import ResearchRequest
from .scoring import ScoredOpportunity

logger = logging.getLogger("saas_research.pipeline.ideas")


@dataclass
class Idea:
    ref: str
    opportunity: ScoredOpportunity
    draft: IdeaDraft
    score: int
    evidence: list[EvidenceRecord]
    evidence_inherited: bool = False
    recommended: bool = False
    low_confidence: bool = False
    approval_summary: str = ""
    extra: dict = field(default_factory=dict)


IDEAS_SYSTEM = f"""You are a pragmatic SaaS product strategist. Propose software products that solve the given \
evidenced opportunities for the stated customer segment.
{GROUNDING_RULES}
- Every idea must reference exactly one opportunity_id from the input.
- source_ids: only ids listed under that opportunity's evidence.
- key_features: the few features that make an MVP useful; mvp_scope: what to build first (weeks, not months).
- pricing_model: a concrete, plausible model (e.g. per-seat monthly) — label it as a hypothesis.
- risks: honest risks (market, technical, regulatory, distribution).
- idea_score: your honest confidence 0-100 that this is viable."""


def generate_ideas(llm: LLMProvider, req: ResearchRequest, opportunities: list[ScoredOpportunity],
                   registry: EvidenceRegistry) -> list[Idea]:
    if not opportunities:
        return []
    by_oid = {o.problem.oid: o for o in opportunities}
    payload = {
        "task": "generate_ideas", "industry": req.industry, "customer_segment": req.customer_segment,
        "regions": list(req.regions), "language": req.language, "user_notes": req.notes,
        "max_ideas": req.max_ideas,
        "opportunities": [{"opportunity_id": o.problem.oid, "title": o.problem.title,
                           "problem_statement": o.problem.problem_statement, "score": o.score,
                           "target_segment": o.problem.target_segment, "competitors": o.problem.competitors,
                           "evidence": [e.prompt_view(400) for e in o.problem.evidence]} for o in opportunities],
    }
    out = llm.generate(system=IDEAS_SYSTEM,
                       prompt=f"Propose up to {req.max_ideas} ideas, best first.\n{render_input(payload)}",
                       output_model=IdeaDrafts)
    ideas: list[Idea] = []
    names: set[str] = set()
    for d in out.ideas:
        opp = by_oid.get(d.opportunity_id.strip())
        name = truncate(squash(d.name), 200)
        if opp is None:
            logger.info("dropping idea %r: unknown opportunity_id %r", name, d.opportunity_id)
            continue
        if not name or name.lower() in names or not d.summary.strip():
            continue
        names.add(name.lower())
        allowed = {e.ref for e in opp.problem.evidence}
        cited = [e for e in registry.resolve(d.source_ids) if e.ref in allowed]
        inherited = not cited
        evidence = cited or list(opp.problem.evidence)
        score = d.idea_score if opp.score is None else round(0.6 * opp.score + 0.4 * d.idea_score)
        ideas.append(Idea(ref=stable_ref("idea", opp.ref, name.lower()), opportunity=opp,
                          draft=d.model_copy(update={"name": name}), score=max(0, min(100, score)),
                          evidence=evidence, evidence_inherited=inherited))
        if len(ideas) >= req.max_ideas:
            break
    ideas.sort(key=lambda i: -i.score)
    return ideas


def build_approval_summary(idea: Idea) -> str:
    opp, d = idea.opportunity, idea.draft
    lines = []
    if idea.low_confidence:
        lines.append("LOW CONFIDENCE — no idea reached the recommendation threshold; submitted as the best "
                     "available option for your judgement.")
    lines.append(f"Recommendation: {d.name} — score {idea.score}/100.")
    opp_score = f"{opp.score}/100" if opp.score is not None else "unscored"
    lines.append(f"Why: addresses '{opp.problem.title}' (opportunity {opp_score}, pain "
                 f"{opp.problem.pain_severity}/5).")
    if opp.ratings is not None:
        r = opp.ratings
        lines.append(f"Ratings: pain {r.pain}, frequency {r.frequency}, willingness to pay {r.willingness_to_pay}, "
                     f"competition gap {r.competition_gap}, feasibility {r.feasibility} (1-5).")
    if opp.rationale:
        lines.append(f"Analyst note: {truncate(squash(opp.rationale), 600)}")
    types = sorted({e.source_type for e in idea.evidence})
    lines.append(f"Evidence: {len(idea.evidence)} retrieved source(s) ({', '.join(types)})"
                 + (" — inherited from the opportunity" if idea.evidence_inherited else "") + ".")
    if opp.problem.competitors:
        lines.append("Competitors seen: " + ", ".join(c["name"] for c in opp.problem.competitors[:6]) + ".")
    if d.risks:
        lines.append("Risks: " + "; ".join(truncate(squash(r), 200) for r in d.risks[:5]) + ".")
    if d.pricing_model:
        lines.append(f"Pricing hypothesis: {truncate(squash(d.pricing_model), 300)}.")
    lines.append("All claims are AI-generated from the cited sources; verify before investing.")
    return truncate("\n".join(lines), 5000)


def mark_recommendations(ideas: list[Idea], min_score: int) -> list[Idea]:
    for idea in ideas:
        idea.recommended = idea.score >= min_score
    if ideas and not any(i.recommended for i in ideas):
        best = max(ideas, key=lambda i: i.score)
        best.recommended, best.low_confidence = True, True
    for idea in ideas:
        if idea.recommended:
            idea.approval_summary = build_approval_summary(idea)
    return ideas
