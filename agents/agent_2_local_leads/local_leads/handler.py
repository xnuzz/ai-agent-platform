"""LOCAL_LEAD_DISCOVERY handler (docs/AGENT_2_CONTRACT.md).

location -> businesses -> website scan -> problems -> scored leads (QUALIFIED / DISQUALIFIED)
         -> per qualified lead: project brief + outreach draft written in parallel
         -> Result Bundle per batch (`batch_size` businesses) with evidence for every business and problem.
Stages reported: PLANNING, DISCOVERING_BUSINESSES, SCANNING_WEBSITES, QUALIFYING, WRITING_BRIEFS,
DRAFTING_OUTREACH, SUBMITTING. The agent only *requests* approval; it never approves or sends.
"""
from __future__ import annotations

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from platform_sdk import PlatformError, RetryableError, TaskCancelled, TaskContext

from .analyzer import ScanResult, WebsiteAnalyzer
from .briefs import Estimate, build_estimate
from .bundle import BatchBundle, Refs, clean_email, clean_url
from .config import Settings
from .contacts import ContactChoice, choose_contact
from .discovery import DiscoveryProvider, DiscoveryUnavailable, build_discovery
from .llm import LLMProvider, build_llm
from .models import DiscoveredBusiness, Finding, TaskInput
from .problems import ALL_CODES, spec
from .scoring import Assessment, score_lead
from .writing import Writer, Written

logger = logging.getLogger("local_leads.handler")
TASK_TYPE = "LOCAL_LEAD_DISCOVERY"


@dataclass
class LeadWork:
    business: DiscoveredBusiness
    refs: Refs
    scan: ScanResult | None
    findings: list[Finding]
    contact: ContactChoice | None
    assessment: Assessment | None = None
    suppressed: bool = False
    estimate: Estimate | None = None
    brief: Written | None = None
    outreach: Written | None = None


def _domain(url: str) -> str:
    host = (urlsplit(url if "://" in url else "http://" + url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


class LocalLeadsAgent:
    """Callable handler: AgentWorker(client, {"LOCAL_LEAD_DISCOVERY": LocalLeadsAgent(settings)})."""

    def __init__(self, settings: Settings, *, discovery: DiscoveryProvider | None = None,
                 llm: LLMProvider | None | str = "auto", analyzer: WebsiteAnalyzer | None = None):
        self.settings = settings
        self.discovery = discovery or build_discovery(settings)
        self.llm = build_llm(settings) if llm == "auto" else llm
        self.writer = Writer(self.llm)
        self.analyzer = analyzer or WebsiteAnalyzer(settings.crawler)

    def close(self) -> None:
        self.analyzer.close()
        self.discovery.close()

    # ================================================================== entry point
    def __call__(self, ctx: TaskContext) -> dict:
        inp = TaskInput.parse(ctx.input)
        unknown_checks = sorted(set(inp.checks) - ALL_CODES)
        wanted = (set(inp.checks) & ALL_CODES) or set(ALL_CODES)
        if inp.checks and not set(inp.checks) & ALL_CODES:
            logger.warning("task %s: none of the requested checks are known (%s); running all", ctx.task.id,
                           inp.checks)
        ctx.progress(2, stage="PLANNING", message=(
            f"{inp.location.label} (radius {inp.location.radius_km} km), categories: "
            f"{', '.join(inp.categories) or 'any'}, up to {inp.max_businesses} businesses, "
            f"min score {inp.min_score}")[:500])

        ctx.progress(5, stage="DISCOVERING_BUSINESSES",
                     message=f"Searching {self.discovery.name} for businesses in {inp.location.label}")
        try:
            found = self.discovery.discover(inp, limit=inp.max_businesses)
        except DiscoveryUnavailable as exc:
            raise RetryableError(str(exc)) from exc
        businesses = self._dedupe(found)[: inp.max_businesses]
        stats: Counter = Counter(businesses_found=len(businesses))
        ctx.progress(10, stage="DISCOVERING_BUSINESSES", message=f"Found {len(businesses)} businesses")

        size = self.settings.batch_size
        batches = [businesses[i:i + size] for i in range(0, len(businesses), size)]
        for n, batch in enumerate(batches):
            self._run_batch(ctx, inp, wanted, batch, n, len(batches), len(businesses), stats)

        ctx.progress(100, stage="SUBMITTING", message="Done")
        return {
            **dict(stats), "batches": len(batches), "min_score": inp.min_score,
            "checks": sorted(wanted) if inp.checks else "ALL", "unknown_checks": unknown_checks,
            "discovery_provider": self.discovery.name,
            "llm_provider": self.llm.describe() if self.llm else "template",
        }

    @staticmethod
    def _dedupe(found: list[DiscoveredBusiness]) -> list[DiscoveredBusiness]:
        """One business per provider id and per website domain (the backend dedupes by domain too)."""
        seen_ids, seen_domains, out = set(), set(), []
        for b in found:
            dom = _domain(b.website) if b.website else ""
            if (b.provider, b.provider_id) in seen_ids or (dom and dom in seen_domains):
                continue
            seen_ids.add((b.provider, b.provider_id))
            if dom:
                seen_domains.add(dom)
            out.append(b)
        return out

    # ================================================================== one batch
    def _run_batch(self, ctx, inp: TaskInput, wanted: set[str], batch: list[DiscoveredBusiness], n: int,
                   n_batches: int, total: int, stats: Counter) -> None:
        span = 88 / n_batches
        base = 10 + n * span
        pct = lambda frac: min(99, int(base + span * frac))  # noqa: E731
        first, last = n * self.settings.batch_size + 1, n * self.settings.batch_size + len(batch)
        label = f"businesses {first}-{last} of {total}"

        # ---- scan websites (parallel; politeness is per host inside the fetcher)
        ctx.progress(pct(0.0), stage="SCANNING_WEBSITES", message=f"Scanning websites of {label}")
        scans = self._scan_all(batch, wanted)
        ctx.check_cancelled()

        # ---- qualify
        ctx.progress(pct(0.4), stage="QUALIFYING", message=f"Scoring {label}")
        work = [self._qualify(b, scans.get(b.key), inp, wanted) for b in batch]
        qualified = [w for w in work if w.assessment.qualified]
        self._mark_suppressed(ctx, qualified)

        # ---- briefs + outreach drafted in parallel for every qualified lead
        ctx.progress(pct(0.55), stage="WRITING_BRIEFS",
                     message=f"Writing {len(qualified)} project brief(s) and outreach drafts")
        self._write(qualified, inp)
        ctx.progress(pct(0.8), stage="DRAFTING_OUTREACH",
                     message=f"{sum(1 for w in qualified if w.outreach)} outreach draft(s) ready")

        # ---- submit
        ctx.progress(pct(0.9), stage="SUBMITTING", message=f"Submitting results for {label}")
        bundle = self._bundle(work, inp)
        try:
            report = ctx.submit(bundle.payload())
        except PlatformError as exc:
            if exc.code in ("cancel_requested", "lease_lost", "task_not_running"):
                raise TaskCancelled() from exc
            raise
        self._count(stats, work, report)

    def _scan_all(self, batch: list[DiscoveredBusiness], wanted: set[str]) -> dict[str, ScanResult]:
        targets = [b for b in batch if clean_url(b.website)]   # malformed listing URLs are never requested
        if not targets:
            return {}

        def scan(b: DiscoveredBusiness) -> ScanResult:
            try:
                return self.analyzer.analyze(clean_url(b.website), category=b.category, wanted=wanted)
            except Exception as exc:  # noqa: BLE001 - one broken site must not fail the task
                logger.exception("scan failed for %s", b.website)
                return ScanResult(url=b.website, skipped_reason=f"scanner error: {type(exc).__name__}",
                                  retrieved_at=datetime.now(timezone.utc).isoformat())

        with ThreadPoolExecutor(max_workers=self.settings.crawler.concurrency,
                                thread_name_prefix="scan") as pool:
            return {b.key: r for b, r in zip(targets, pool.map(scan, targets), strict=True)}

    def _qualify(self, b: DiscoveredBusiness, scan: ScanResult | None, inp: TaskInput, wanted: set[str]
                 ) -> LeadWork:
        findings: list[Finding] = []
        if not b.website and "NO_WEBSITE" in wanted:
            findings.append(Finding(code="NO_WEBSITE", severity=spec("NO_WEBSITE").severity,
                                    title=spec("NO_WEBSITE").title, url=b.listing_url,
                                    description=f"No website is listed for {b.name} in its "
                                                f"{b.provider} listing.", facts={"listing": b.listing_url}))
        elif scan is not None:
            findings.extend(f for f in scan.findings if f.code in wanted)
        candidates = [(b.email, f"{b.provider} listing")] if b.email else []
        if scan is not None:
            candidates += [(e, f"website {scan.final_url or scan.url}") for e in scan.emails]
        contact = choose_contact(candidates, business_name=b.name, website=b.website,
                                 country_code=b.country_code or inp.location.country_code)
        note = ""
        if b.website and not clean_url(b.website):
            note = f"Listed website value {b.website[:100]!r} is not a valid URL; not analysed."
        elif scan is not None and not scan.scanned and scan.skipped_reason and not findings:
            note = f"Website not analysed ({scan.skipped_reason})."
        assessment = score_lead(findings, contact, min_score=inp.min_score, scan_note=note)
        return LeadWork(business=b, refs=Refs(b), scan=scan, findings=findings, contact=contact,
                        assessment=assessment)

    @staticmethod
    def _mark_suppressed(ctx, qualified: list[LeadWork]) -> None:
        emails = sorted({w.contact.email for w in qualified if w.contact})
        phone = lambda w: w.business.phone.strip()[:50]  # noqa: E731 - backend field limit
        phones = sorted({phone(w) for w in qualified if phone(w)})
        if not emails and not phones:
            return
        res = ctx.check_suppression(emails=emails, phones=phones)
        bad_e = {e.lower() for e in res.get("suppressed_emails", [])}
        bad_p = set(res.get("suppressed_phones", []))
        for w in qualified:
            if (w.contact and w.contact.email.lower() in bad_e) or (phone(w) and phone(w) in bad_p):
                w.suppressed = True

    def _facts(self, w: LeadWork, inp: TaskInput) -> dict:
        b = w.business
        return {
            "language": inp.language, "score": w.assessment.score,
            "business": {"name": b.name, "category": b.category, "city": b.city or inp.location.city,
                         "country_code": b.country_code or inp.location.country_code, "website": b.website,
                         "domain": _domain(b.website) if b.website else ""},
            "problems": [{"code": f.code, "title": f.title, "severity": f.severity, "description": f.description}
                         for f in w.findings],
            "estimate": w.estimate.as_facts(), "task_notes": inp.notes[:500],
        }

    def _write(self, qualified: list[LeadWork], inp: TaskInput) -> None:
        if not qualified:
            return
        for w in qualified:
            cms = (w.scan.facts.get("cms", "") if w.scan else "") or ""
            w.estimate = build_estimate(w.findings, hourly_rate=self.settings.hourly_rate,
                                        currency=self.settings.currency or "EUR", cms=cms)
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="write") as pool:
            jobs = []
            for w in qualified:
                facts = self._facts(w, inp)
                jobs.append((w, "brief", pool.submit(self.writer.brief, facts)))
                if w.contact and not w.suppressed:  # check_suppression ran before drafting
                    jobs.append((w, "outreach", pool.submit(self.writer.outreach, facts)))
            for w, kind, fut in jobs:
                setattr(w, kind, fut.result())

    # ================================================================== bundle
    def _bundle(self, work: list[LeadWork], inp: TaskInput) -> BatchBundle:
        bb = BatchBundle()
        now = datetime.now(timezone.utc).isoformat()
        for w in work:
            b, refs = w.business, w.refs
            listing = bb.listing_evidence(b, refs, now)
            ev = [listing]
            if w.scan is not None:
                ev.append(bb.scan_evidence(w.scan, refs))
            problems = []
            for i, f in enumerate(w.findings):
                if f.code == "NO_WEBSITE":
                    problems.append(bb.problem(f, [listing]))
                else:
                    problems.append(bb.problem(f, [refs.scan, bb.finding_evidence(f, refs, i, now)]))
            business_email = w.contact.email if w.contact else ""
            bb.business(b, refs, email=business_email, evidence_refs=list(ev))
            contact = {"phone": b.phone[:50]}
            if w.contact:
                contact.update(email=clean_email(w.contact.email), email_type=w.contact.email_type,
                               legal_basis=w.contact.legal_basis, legal_basis_note=w.contact.legal_basis_note)
            bb.lead(refs, status=w.assessment.status, score=w.assessment.score, notes=w.assessment.notes,
                    problems=problems, contact=contact, evidence_refs=list(ev))
            if w.assessment.qualified and w.brief is not None:
                self._brief_and_campaign(bb, w, problems, ev, inp)
        return bb

    def _brief_and_campaign(self, bb: BatchBundle, w: LeadWork, problems, ev, inp: TaskInput) -> None:
        est, brief, b = w.estimate, w.brief, w.business
        if w.suppressed:
            outreach_note = "No outreach drafted: the contact is on the workspace suppression list."
        elif not w.contact:
            outreach_note = "No outreach drafted: no usable business e-mail address was found."
        elif w.outreach is None:
            outreach_note = "No outreach drafted."
        else:
            outreach_note = (f"Outreach e-mail drafted to {w.contact.email} ({w.contact.email_type}, legal basis "
                             f"{w.contact.legal_basis}); see linked campaign.")
        writer_note = f"Text by {brief.author}" + (f" ({brief.note})" if brief.note else "") + "."
        bb.brief(w.refs, text=brief.data, problems=problems, estimate=est, evidence_refs=list(ev),
                 submit=not w.suppressed,
                 approval_summary=f"{brief.data['approval_summary']} {outreach_note} {writer_note}")
        if w.outreach is None or w.suppressed or not w.contact:
            return
        o = w.outreach
        lb_note = (" Legal basis is UNKNOWN: the backend blocks sending until a reviewer sets it on the lead."
                   if w.contact.legal_basis == "UNKNOWN" else "")
        bb.campaign(
            w.refs, name=f"Website project offer - {b.name}",
            offer={"headline": brief.data["title"], "value_proposition": brief.data["summary"],
                   "pricing": f"Estimated {est.currency} {est.budget_min:,.0f}-{est.budget_max:,.0f} "
                              f"({est.hours_min}-{est.hours_max} hours)",
                   "call_to_action": "Short call or e-mail with the detailed proposal"},
            subject=o.data["subject"], body=o.data["body"],
            language="en" if o.author == "template" else inp.language,
            approval_summary=(f"First e-mail (step 1) to {w.contact.email} ({w.contact.email_type}) for "
                              f"'{brief.data['title']}'. Score {w.assessment.score}/100.{lb_note} Text by "
                              f"{o.author}{f' ({o.note})' if o.note else ''}."))

    @staticmethod
    def _count(stats: Counter, work: list[LeadWork], report: dict) -> None:
        stats["scanned"] += sum(1 for w in work if w.scan is not None and w.scan.scanned)
        stats["qualified"] += sum(1 for w in work if w.assessment.qualified)
        stats["disqualified"] += sum(1 for w in work if not w.assessment.qualified)
        stats["suppressed_contacts"] += sum(1 for w in work if w.suppressed)
        stats["briefs"] += sum(1 for w in work if w.brief is not None)
        stats["campaigns"] += sum(1 for w in work if w.outreach is not None and not w.suppressed and w.contact)
        stats["approvals_requested"] += len(report.get("approvals_requested") or [])
        stats["skipped_items"] += len(report.get("skipped") or [])
        stats["llm_written"] += sum(1 for w in work for x in (w.brief, w.outreach) if x and x.author != "template")
        stats["template_written"] += sum(1 for w in work for x in (w.brief, w.outreach)
                                         if x and x.author == "template")
