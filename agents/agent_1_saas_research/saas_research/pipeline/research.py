"""Step 1 (SAAS_OPPORTUNITY_RESEARCH): plan searches -> gather real sources -> extract evidenced problems."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..evidence import EvidenceRecord, EvidenceRegistry
from ..llm.base import LLMProvider, render_input
from ..schemas import ProblemExtraction
from ..sources.base import SearchProvider
from .common import GROUNDING_RULES, SEGMENT_TERMS, squash, truncate

logger = logging.getLogger("saas_research.pipeline.research")


@dataclass(frozen=True)
class ResearchRequest:
    """SAAS_OPPORTUNITY_RESEARCH input with contract defaults (docs/AGENT_1_CONTRACT.md)."""
    industry: str
    regions: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    customer_segment: str = "ANY"
    max_opportunities: int = 5
    max_ideas: int = 3
    language: str = "en"
    notes: str = ""

    @classmethod
    def from_input(cls, data: dict) -> "ResearchRequest":
        industry = squash(str(data.get("industry") or ""))
        if not industry:
            from ..errors import InvalidTaskInput
            raise InvalidTaskInput("input.industry is required")
        segment = str(data.get("customer_segment") or "ANY").upper()
        return cls(
            industry=industry[:200],
            regions=tuple(str(r).upper()[:2] for r in (data.get("regions") or []) if r),
            keywords=tuple(squash(str(k))[:100] for k in (data.get("keywords") or []) if squash(str(k)))[:20],
            customer_segment=segment if segment in SEGMENT_TERMS else "ANY",
            max_opportunities=max(1, min(int(data.get("max_opportunities") or 5), 20)),
            max_ideas=max(1, min(int(data.get("max_ideas") or 3), 10)),
            language=str(data.get("language") or "en")[:10],
            notes=str(data.get("notes") or "")[:2000],
        )

    @property
    def segment_term(self) -> str:
        return SEGMENT_TERMS[self.customer_segment]


@dataclass(frozen=True)
class PlannedQuery:
    query: str
    country: str | None = None


@dataclass
class Problem:
    oid: str
    title: str
    problem_statement: str
    target_segment: str
    pain_severity: int
    evidence: list[EvidenceRecord]
    competitors: list[dict] = field(default_factory=list)


def plan_queries(req: ResearchRequest, max_queries: int | None = None) -> list[PlannedQuery]:
    """Deterministic search plan covering pain points, complaints, workarounds and competitor reviews.
    Keywords get their own queries; regions are spread round-robin so each region is searched."""
    seg, ind = req.segment_term, req.industry
    base = [
        f"{ind} {seg} biggest operational challenges",
        f"{ind} software complaints",
        f"{ind} manual process spreadsheet frustrating",
        f"{ind} {seg} pain points forum",
        f"{ind} software alternatives reviews",
        f"{ind} workflow automation problems",
    ]
    kw_queries = []
    for kw in req.keywords:
        kw_queries += [f"{ind} {kw} problems", f"{kw} software reviews"]
    # Interleave so keyword queries are not crowded out by the cap.
    texts: list[str] = []
    for i in range(max(len(base), len(kw_queries))):
        if i < len(kw_queries):
            texts.append(kw_queries[i])
        if i < len(base):
            texts.append(base[i])
    limit = max_queries or min(12, 4 + req.max_opportunities + len(req.keywords))
    limit = max(limit, len(req.regions))
    seen: dict[str, None] = {}
    for t in texts:
        seen.setdefault(squash(t), None)
    queries = list(seen)[:limit]
    if req.regions:
        while len(queries) < len(req.regions):  # guarantee one query per region
            queries.append(queries[len(queries) % max(1, len(seen))])
        return [PlannedQuery(q, req.regions[i % len(req.regions)]) for i, q in enumerate(queries)]
    return [PlannedQuery(q, None) for q in queries]


def gather_sources(search: SearchProvider, queries: list[PlannedQuery], registry: EvidenceRegistry, *,
                   results_per_query: int, language: str | None = None, on_query=None) -> int:
    """Run all queries; register every result as candidate evidence. Returns number of new sources."""
    before = len(registry)
    for i, q in enumerate(queries):
        results = search.search(q.query, max_results=results_per_query, country=q.country, language=language)
        for r in results:
            registry.add_search_result(r)
        if on_query:
            on_query(i + 1, len(queries))
    return len(registry) - before


EXTRACT_SYSTEM = f"""You are a B2B SaaS market researcher. From the retrieved web sources, identify concrete, \
recurring business problems in the given industry that software could solve.
{GROUNDING_RULES}
- Each problem must cite at least one source id that actually describes or evidences the problem.
- Mention competitors only if a cited source names them; set source_id to that source.
- pain_severity: 1 (minor annoyance) .. 5 (costs significant money/time or blocks work)."""


def extract_problems(llm: LLMProvider, req: ResearchRequest, registry: EvidenceRegistry, *,
                     max_candidates: int, max_sources: int = 120) -> list[Problem]:
    """LLM extraction + citation enforcement: problems without at least one resolvable source are dropped."""
    if not len(registry):
        return []
    payload = {
        "task": "extract_problems",
        "industry": req.industry, "customer_segment": req.customer_segment, "regions": list(req.regions),
        "keywords": list(req.keywords), "language": req.language, "user_notes": req.notes,
        "max_problems": max_candidates,
        "sources": registry.prompt_sources(limit=max_sources),
    }
    prompt = (f"Identify up to {max_candidates} distinct problems.\n{render_input(payload)}")
    out = llm.generate(system=EXTRACT_SYSTEM, prompt=prompt, output_model=ProblemExtraction)
    problems: list[Problem] = []
    seen_titles: set[str] = set()
    for cand in out.problems:
        evidence = registry.resolve(cand.source_ids)
        title = truncate(squash(cand.title), 300)
        if not evidence:
            logger.info("dropping unsupported problem (no resolvable sources): %s", title)
            continue
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        competitors = []
        for c in cand.competitors:
            src = registry.get(c.source_id) if c.source_id else None
            if src is None:
                logger.info("dropping competitor without cited source: %s", c.name)
                continue
            competitors.append({"name": truncate(squash(c.name), 200), "url": src.url,
                                "notes": truncate(squash(c.notes) or f"Mentioned in: {src.title}", 2000)})
        problems.append(Problem(oid=f"O{len(problems) + 1}", title=title,
                                problem_statement=truncate(cand.problem_statement.strip(), 4000),
                                target_segment=truncate(squash(cand.target_segment), 300),
                                pain_severity=cand.pain_severity, evidence=evidence, competitors=competitors))
        if len(problems) >= max_candidates:
            break
    return problems
