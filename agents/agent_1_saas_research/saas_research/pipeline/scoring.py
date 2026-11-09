"""Step 2: opportunity scoring.

The LLM rates each evidenced problem on five 1-5 dimensions; the score itself is computed deterministically here
so it is explainable and testable:

    base  = Σ weight_d · (rating_d − 1) / 4 · 100
    score = round(base · evidence_factor)      evidence_factor = 0.85 (1 source), 0.93 (2), 1.0 (≥3)

Problems the model did not rate keep `score=None` (never invented) and sort last.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..llm.base import LLMProvider, render_input
from ..schemas import DimensionRatings, OpportunityRatings
from .common import GROUNDING_RULES, stable_ref
from .research import Problem, ResearchRequest

logger = logging.getLogger("saas_research.pipeline.scoring")

WEIGHTS = {"pain": 0.30, "frequency": 0.20, "willingness_to_pay": 0.20, "competition_gap": 0.15,
           "feasibility": 0.15}
EVIDENCE_FACTOR = {1: 0.85, 2: 0.93}


def compute_score(ratings: DimensionRatings, evidence_count: int) -> int:
    base = sum(w * (getattr(ratings, d) - 1) / 4 * 100 for d, w in WEIGHTS.items())
    factor = EVIDENCE_FACTOR.get(evidence_count, 1.0) if evidence_count > 0 else 0.0
    return max(0, min(100, round(base * factor)))


@dataclass
class ScoredOpportunity:
    problem: Problem
    ref: str
    score: int | None
    ratings: DimensionRatings | None
    rationale: str = ""
    industry: str = ""
    market_signals: dict = field(default_factory=dict)


SCORING_SYSTEM = f"""You are a SaaS investment analyst. Rate each opportunity strictly from the evidence given.
{GROUNDING_RULES}
Dimensions (1 = weak, 5 = strong): pain, frequency (how often it occurs), willingness_to_pay, competition_gap \
(5 = poorly served by existing tools), feasibility (5 = a small team can build an MVP quickly).
Return one rating per opportunity_id; keep rationale short and tied to the evidence."""


def score_opportunities(llm: LLMProvider, req: ResearchRequest, problems: list[Problem]) -> list[ScoredOpportunity]:
    """Rate, score, rank and cut to `req.max_opportunities`."""
    if not problems:
        return []
    payload = {
        "task": "score_opportunities", "industry": req.industry, "customer_segment": req.customer_segment,
        "language": req.language, "user_notes": req.notes,
        "opportunities": [{"opportunity_id": p.oid, "title": p.title, "problem_statement": p.problem_statement,
                           "target_segment": p.target_segment, "pain_severity": p.pain_severity,
                           "competitors": [c["name"] for c in p.competitors],
                           "evidence": [e.prompt_view(400) for e in p.evidence]} for p in problems],
    }
    out = llm.generate(system=SCORING_SYSTEM, prompt=f"Rate every opportunity.\n{render_input(payload)}",
                       output_model=OpportunityRatings)
    by_id = {}
    for r in out.ratings:
        by_id.setdefault(r.opportunity_id.strip(), r)
    scored: list[ScoredOpportunity] = []
    used_refs: set[str] = set()
    for p in problems:
        rating = by_id.get(p.oid)
        ref = stable_ref("op", req.industry.lower(), p.title.lower())
        while ref in used_refs:
            ref = stable_ref("op", ref)
        used_refs.add(ref)
        types: dict[str, int] = {}
        for e in p.evidence:
            types[e.source_type] = types.get(e.source_type, 0) + 1
        signals = {"evidence_count": len(p.evidence), "source_types": types, "pain_severity": p.pain_severity,
                   "scoring_method": "weighted_dimensions_v1", "weights": WEIGHTS}
        if rating is None:
            logger.info("opportunity %s not rated by the model; score left empty", p.oid)
            signals["rating_missing"] = True
            scored.append(ScoredOpportunity(p, ref, None, None, "", req.industry, signals))
            continue
        signals["ratings"] = rating.ratings.model_dump()
        signals["rationale"] = rating.rationale.strip()[:2000]
        scored.append(ScoredOpportunity(p, ref, compute_score(rating.ratings, len(p.evidence)), rating.ratings,
                                        rating.rationale.strip(), req.industry, signals))
    scored.sort(key=lambda s: (s.score is None, -(s.score or 0), -len(s.problem.evidence)))
    return scored[: req.max_opportunities]
