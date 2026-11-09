"""Task handlers for `platform_sdk.AgentWorker`.

SAAS_OPPORTUNITY_RESEARCH:  PLANNING -> SEARCHING -> ANALYZING_COMPETITORS -> SCORING -> (submit evidence +
                            opportunities) -> GENERATING_IDEAS -> SUBMITTING (ideas, submit_for_approval)
SAAS_CUSTOMER_RESEARCH:     PLANNING -> FINDING_CUSTOMERS -> (suppression check) -> SUBMITTING (evidence,
                            businesses, leads) -> DRAFTING_OUTREACH -> SUBMITTING (campaign, submit_for_approval)

Handlers never approve or send. Exceptions propagate to the SDK worker, which maps
ProviderTransientError (a RetryableError) -> retryable_error, TaskCancelled -> CANCELLED, anything else -> agent_error.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from platform_sdk import TaskContext

from .config import Settings
from .evidence import EvidenceRegistry
from .llm.base import LLMProvider
from .pipeline import bundles as B
from .pipeline.customers import (CustomerRequest, assess_candidates, find_contacts, plan_customer_queries,
                                 search_candidates)
from .pipeline.ideas import generate_ideas, mark_recommendations
from .pipeline.outreach import draft_messages, draft_offer
from .pipeline.research import ResearchRequest, extract_problems, gather_sources, plan_queries
from .pipeline.scoring import score_opportunities
from .sources.base import PageFetcher, SearchProvider

logger = logging.getLogger("saas_research.handlers")


@dataclass
class Providers:
    llm: LLMProvider
    search: SearchProvider
    fetcher: PageFetcher


@dataclass(frozen=True)
class PipelineOptions:
    results_per_query: int = 8
    batch_size: int = 100
    idea_approval_min_score: int = 60
    lead_min_fit_score: int = 50
    lead_qualified_min_fit: int = 70
    max_customer_queries: int = 8

    @classmethod
    def from_settings(cls, s: Settings) -> "PipelineOptions":
        return cls(results_per_query=s.search_results_per_query, batch_size=s.batch_size,
                   idea_approval_min_score=s.idea_approval_min_score, lead_min_fit_score=s.lead_min_fit_score)


def _progress(ctx: TaskContext, pct: int, stage: str, message: str | None = None) -> None:
    ctx.progress(max(0, min(100, pct)), stage=stage, message=(message or "")[:500] or None)


class Agent1Handlers:
    def __init__(self, providers: Providers, options: PipelineOptions | None = None):
        self.p = providers
        self.o = options or PipelineOptions()

    def as_dict(self) -> dict:
        return {"SAAS_OPPORTUNITY_RESEARCH": self.opportunity_research,
                "SAAS_CUSTOMER_RESEARCH": self.customer_research}

    # ------------------------------------------------------------------ SAAS_OPPORTUNITY_RESEARCH
    def opportunity_research(self, ctx: TaskContext) -> dict:
        req = ResearchRequest.from_input(ctx.input)
        _progress(ctx, 5, "PLANNING", f"Planning research for '{req.industry}'")
        queries = plan_queries(req)
        registry = EvidenceRegistry("S")
        submitter = B.BatchSubmitter(ctx.submit, "SAAS_OPPORTUNITY_RESEARCH", self.o.batch_size)

        _progress(ctx, 10, "SEARCHING", f"Running {len(queries)} searches")
        gather_sources(self.p.search, queries, registry, results_per_query=self.o.results_per_query,
                       language=req.language,
                       on_query=lambda i, n: _progress(ctx, 10 + 25 * i // n, "SEARCHING",
                                                       f"Search {i}/{n}: {len(registry)} sources"))
        if not len(registry):
            _progress(ctx, 95, "SUBMITTING", "No sources found; nothing to submit")
            return {"opportunities": 0, "ideas": 0, "sources": 0, "queries": len(queries),
                    "note": "no search results"}

        _progress(ctx, 40, "ANALYZING_COMPETITORS", f"Extracting problems and competitors from {len(registry)} sources")
        problems = extract_problems(self.p.llm, req, registry, max_candidates=min(20, req.max_opportunities * 2))

        _progress(ctx, 55, "SCORING", f"Scoring {len(problems)} evidenced problems")
        opportunities = score_opportunities(self.p.llm, req, problems)
        for o in opportunities:
            registry.cite(o.problem.evidence)
        submitter.send_batched("opportunities", [B.opportunity_item(o) for o in opportunities],
                               evidence=registry.pending_bundle_items())

        _progress(ctx, 70, "GENERATING_IDEAS", f"Generating up to {req.max_ideas} ideas")
        ideas = mark_recommendations(generate_ideas(self.p.llm, req, opportunities, registry),
                                     self.o.idea_approval_min_score)
        for i in ideas:
            registry.cite(i.evidence)

        _progress(ctx, 90, "SUBMITTING", f"Submitting {len(ideas)} ideas")
        submitter.send_batched("software_ideas", [B.idea_item(i) for i in ideas],
                               evidence=registry.pending_bundle_items())
        return {
            "opportunities": len(opportunities), "ideas": len(ideas),
            "ideas_submitted_for_approval": sum(1 for i in ideas if i.recommended),
            "evidence": len(submitter.known.get("evidence", ())), "sources_retrieved": len(registry),
            "queries": len(queries), "llm": f"{self.p.llm.name}:{self.p.llm.model}", "search": self.p.search.name,
        }

    # ------------------------------------------------------------------ SAAS_CUSTOMER_RESEARCH
    def customer_research(self, ctx: TaskContext) -> dict:
        req = CustomerRequest.from_task(ctx.input, ctx.task.context)
        idea_name = req.software_idea.get("name", "")
        _progress(ctx, 5, "PLANNING", f"Planning customer search for '{idea_name}'")
        registry = EvidenceRegistry("S")
        submitter = B.BatchSubmitter(ctx.submit, "SAAS_CUSTOMER_RESEARCH", self.o.batch_size)
        queries = plan_customer_queries(self.p.llm, req, max_queries=self.o.max_customer_queries)

        _progress(ctx, 10, "FINDING_CUSTOMERS", f"Running {len(queries)} searches")
        records = search_candidates(self.p.search, queries, registry, results_per_query=self.o.results_per_query,
                                    language=req.language,
                                    on_query=lambda i, n: _progress(ctx, 10 + 15 * i // n, "FINDING_CUSTOMERS",
                                                                    f"Search {i}/{n}"))
        _progress(ctx, 28, "FINDING_CUSTOMERS", f"Qualifying {len(records)} candidate websites")
        candidates = assess_candidates(self.p.llm, req, records, min_fit=self.o.lead_min_fit_score)
        leads = find_contacts(self.p.fetcher, candidates, registry, max_leads=req.max_leads,
                              on_candidate=lambda i, n: _progress(ctx, 30 + 25 * i // max(n, 1),
                                                                  "FINDING_CUSTOMERS",
                                                                  f"Checked {i}/{n} websites for contact details"))

        # Suppression must be checked before drafting (contract); suppressed recipients are excluded entirely.
        suppressed: set[str] = set()
        if leads:
            resp = ctx.check_suppression(emails=[c.email for c in leads]) or {}
            suppressed = {e.lower() for e in resp.get("suppressed_emails") or []}
        leads = [c for c in leads if c.email.lower() not in suppressed]

        for c in leads:
            registry.cite([c.source] + ([c.contact_evidence] if c.contact_evidence else []))
        _progress(ctx, 60, "SUBMITTING", f"Submitting {len(leads)} businesses and leads")
        for chunk in B.chunked(leads, self.o.batch_size):
            submitter.send(evidence=registry.pending_bundle_items())
            submitter.send(businesses=[B.business_item(c) for c in chunk])
            submitter.send(leads=[B.lead_item(c, self.o.lead_qualified_min_fit) for c in chunk])

        summary = {"queries": len(queries), "candidates": len(candidates), "leads": len(leads),
                   "suppressed_skipped": len(suppressed), "messages": 0, "campaign_submitted_for_approval": False,
                   "llm": f"{self.p.llm.name}:{self.p.llm.model}", "search": self.p.search.name}
        if not leads or "EMAIL" not in req.channels:
            _progress(ctx, 95, "SUBMITTING", "No contactable leads; no campaign drafted" if not leads
                      else "EMAIL channel not requested; no campaign drafted")
            return summary

        _progress(ctx, 65, "DRAFTING_OUTREACH", "Drafting sales offer")
        offer = draft_offer(self.p.llm, req)
        messages = draft_messages(self.p.llm, req, offer, leads,
                                  on_batch=lambda i, n: _progress(ctx, 65 + 25 * i // n, "DRAFTING_OUTREACH",
                                                                  f"Drafted {i}/{n} emails"))
        by_ref = {c.lead_ref: c for c in leads}
        drafted = [by_ref[m.lead_ref] for m in messages]
        unknown_basis = sum(1 for c in drafted if c.email_type != "GENERIC_BUSINESS")
        regions = ", ".join(req.regions) or "global"
        approval_summary = "\n".join([
            f"Outreach for approved idea '{idea_name}': {len(messages)} first-touch email(s) to {len(messages)} "
            f"lead(s) ({regions}).",
            f"Offer: {offer.headline}",
            f"Contacts: {len(drafted) - unknown_basis} generic business address(es) found on the companies' own "
            f"websites (legal basis: legitimate interest, agent assessment); {unknown_basis} address(es) with "
            f"legal basis UNKNOWN — the platform will not send to these until a human sets a basis.",
            f"Suppression list checked: {len(suppressed)} recipient(s) excluded.",
            "Drafts are AI-generated; review tone and claims. Sender identity and opt-out footer are appended by the "
            "platform.",
        ])
        campaign = B.campaign_item(ref=B.stable_campaign_ref(req), name=f"{idea_name} — outreach ({regions})",
                                   offer=offer.model_dump(), messages=messages, submit=bool(messages),
                                   summary=approval_summary)
        _progress(ctx, 92, "SUBMITTING", f"Submitting campaign with {len(messages)} drafts for approval")
        submitter.send(campaigns=[campaign])
        summary.update(messages=len(messages), campaign_submitted_for_approval=bool(messages),
                       legal_basis_unknown=unknown_basis)
        return summary
