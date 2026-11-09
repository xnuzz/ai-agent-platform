"""Step 6: Result Bundle v1.0 building, local contract validation and batched submission.

Builders map pipeline objects to bundle items exactly as docs/API_CONTRACTS.md §Result Bundle defines them.
`validate_bundle` mirrors the backend's rules (allowed sections, ref uniqueness and resolution, enums, lengths,
sequence_step = 1) so contract bugs surface locally with a precise message instead of a 400.
`BatchSubmitter` streams results in batches (evidence first, so later items can reference it).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from platform_sdk import new_bundle

from ..errors import Agent1Error
from .common import stable_ref
from .customers import Candidate, CustomerRequest, legal_basis_for
from .ideas import Idea
from .outreach import DraftMessage
from .scoring import ScoredOpportunity

ALLOWED_SECTIONS = {
    "SAAS_OPPORTUNITY_RESEARCH": ("evidence", "opportunities", "software_ideas"),
    "SAAS_CUSTOMER_RESEARCH": ("evidence", "businesses", "leads", "campaigns"),
}
SECTIONS = ("evidence", "opportunities", "software_ideas", "businesses", "leads", "project_briefs", "campaigns")
SOURCE_TYPES = {"WEB_PAGE", "SEARCH_RESULT", "REVIEW", "FORUM", "DIRECTORY", "SOCIAL", "API", "DOCUMENT",
                "WEBSITE_SCAN", "OTHER"}
EMAIL_TYPES = {"GENERIC_BUSINESS", "PERSONAL_WORK", "UNKNOWN"}
LEGAL_BASES = {"LEGITIMATE_INTEREST", "CONSENT", "UNKNOWN"}
LEAD_STATUSES = {"NEW", "QUALIFIED", "DISQUALIFIED"}
MAX_ITEMS_PER_SECTION = 500


class BundleValidationError(Agent1Error):
    """A bundle this agent built violates the Result Bundle contract (a bug in this agent)."""


# ---------------------------------------------------------------- builders
def opportunity_item(o: ScoredOpportunity) -> dict:
    p = o.problem
    return {"ref": o.ref, "title": p.title, "problem_statement": p.problem_statement, "industry": o.industry[:200],
            "target_segment": p.target_segment, "pain_severity": p.pain_severity, "score": o.score,
            "competitors": p.competitors, "market_signals": o.market_signals,
            "evidence_refs": [e.ref for e in p.evidence]}


def idea_item(i: Idea) -> dict:
    d = i.draft
    return {"ref": i.ref, "opportunity_ref": i.opportunity.ref, "name": d.name, "summary": d.summary.strip(),
            "problem": d.problem.strip(), "solution": d.solution.strip(), "target_customers": d.target_customers,
            "key_features": [f[:500] for f in d.key_features][:50], "pricing_model": d.pricing_model,
            "differentiation": d.differentiation, "risks": [r[:500] for r in d.risks][:50],
            "mvp_scope": d.mvp_scope, "score": i.score, "evidence_refs": [e.ref for e in i.evidence],
            "submit_for_approval": i.recommended, "approval_summary": i.approval_summary if i.recommended else ""}


def business_item(c: Candidate) -> dict:
    refs = [c.source.ref] + ([c.contact_evidence.ref] if c.contact_evidence else [])
    item: dict[str, Any] = {
        "ref": c.ref, "name": c.name, "website": c.website, "email": c.email if c.email_type == "GENERIC_BUSINESS"
        else "", "address": {"city": c.city, "country_code": c.country_code}, "category": c.category,
        "description": c.fit_rationale, "source_data": {"found_via": c.source.url, "agent": "SAAS_RESEARCH"},
        "evidence_refs": list(dict.fromkeys(refs))}
    return item


def lead_item(c: Candidate, qualified_min_fit: int = 70) -> dict:
    basis, note = legal_basis_for(c)
    status = "QUALIFIED" if (c.fit_score >= qualified_min_fit and c.email_type == "GENERIC_BUSINESS") else "NEW"
    refs = [c.source.ref] + ([c.contact_evidence.ref] if c.contact_evidence else [])
    return {"ref": c.lead_ref, "business_ref": c.ref, "status": status, "score": c.fit_score,
            "qualification_notes": c.fit_rationale,
            "contact": {"email": c.email, "email_type": c.email_type, "legal_basis": basis,
                        "legal_basis_note": note},
            "evidence_refs": list(dict.fromkeys(refs))}


def stable_campaign_ref(req: CustomerRequest) -> str:
    idea = req.software_idea
    return stable_ref("camp", str(idea.get("id") or idea.get("name")))


def campaign_item(*, ref: str, name: str, offer: dict, messages: list[DraftMessage], submit: bool,
                  summary: str) -> dict:
    return {"ref": ref, "name": name[:300], "channel": "EMAIL", "offer": offer,
            "messages": [{"lead_ref": m.lead_ref, "subject": m.subject, "body": m.body, "language": m.language[:10],
                          "sequence_step": 1} for m in messages],
            "submit_for_approval": submit, "approval_summary": summary[:5000]}


# ---------------------------------------------------------------- validation
def _fail(path: str, msg: str):
    raise BundleValidationError(f"{path}: {msg}")


def _check_len(item: dict, key: str, limit: int, path: str, required: bool = False):
    val = item.get(key)
    if required and not (isinstance(val, str) and val.strip()):
        _fail(f"{path}.{key}", "required")
    if val is not None and not isinstance(val, str):
        _fail(f"{path}.{key}", "must be a string")
    if val and len(val) > limit:
        _fail(f"{path}.{key}", f"longer than {limit}")


def _check_refs(refs: Iterable[str], known: set[str], path: str):
    for r in refs:
        if r not in known:
            _fail(path, f"unknown ref {r!r}")


def validate_bundle(bundle: dict, task_type: str, known: dict[str, set[str]] | None = None) -> None:
    """Raise BundleValidationError if `bundle` would be rejected by the backend. `known` = refs submitted earlier
    in the same task, per section."""
    known = {s: set(v) for s, v in (known or {}).items()}
    if bundle.get("schema_version") != "1.0":
        _fail("schema_version", "must be '1.0'")
    allowed = ALLOWED_SECTIONS.get(task_type)
    if allowed is None:
        _fail("task_type", f"unsupported {task_type!r}")
    for s in SECTIONS:
        items = bundle.get(s) or []
        if items and s not in allowed:
            _fail(s, f"section not allowed for {task_type}")
        if len(items) > MAX_ITEMS_PER_SECTION:
            _fail(s, f"more than {MAX_ITEMS_PER_SECTION} items")
        refs = [it.get("ref") for it in items]
        if any(not r or not isinstance(r, str) or len(r) > 200 for r in refs):
            _fail(s, "every item needs a ref (str ≤200)")
        if len(set(refs)) != len(refs):
            _fail(s, "duplicate refs in one bundle")
        known.setdefault(s, set()).update(refs)
    ev = known.get("evidence", set())
    for i, e in enumerate(bundle.get("evidence") or []):
        p = f"evidence[{i}]"
        if not str(e.get("url", "")).startswith(("http://", "https://")) or len(e["url"]) > 2000:
            _fail(f"{p}.url", "must be an http(s) URL ≤2000")
        if e.get("source_type", "OTHER") not in SOURCE_TYPES:
            _fail(f"{p}.source_type", "invalid")
        _check_len(e, "title", 500, p)
        _check_len(e, "excerpt", 5000, p)
    for i, o in enumerate(bundle.get("opportunities") or []):
        p = f"opportunities[{i}]"
        _check_len(o, "title", 300, p, required=True)
        _check_len(o, "problem_statement", 100000, p, required=True)
        _check_len(o, "target_segment", 300, p)
        if o.get("pain_severity") is not None and not 1 <= o["pain_severity"] <= 5:
            _fail(f"{p}.pain_severity", "1..5")
        if o.get("score") is not None and not 0 <= o["score"] <= 100:
            _fail(f"{p}.score", "0..100")
        if not o.get("evidence_refs"):
            _fail(f"{p}.evidence_refs", "Agent 1 contract: at least one evidence item")
        _check_refs(o.get("evidence_refs", []), ev, f"{p}.evidence_refs")
        for j, c in enumerate(o.get("competitors") or []):
            _check_len(c, "name", 200, f"{p}.competitors[{j}]", required=True)
            if c.get("url") and (len(c["url"]) > 500 or not c["url"].startswith(("http://", "https://"))):
                _fail(f"{p}.competitors[{j}].url", "http(s) URL ≤500")
    for i, d in enumerate(bundle.get("software_ideas") or []):
        p = f"software_ideas[{i}]"
        _check_len(d, "name", 200, p, required=True)
        _check_len(d, "summary", 100000, p, required=True)
        _check_len(d, "approval_summary", 5000, p)
        if d.get("score") is not None and not 0 <= d["score"] <= 100:
            _fail(f"{p}.score", "0..100")
        if not d.get("evidence_refs"):
            _fail(f"{p}.evidence_refs", "Agent 1 contract: at least one evidence item")
        _check_refs(d.get("evidence_refs", []), ev, f"{p}.evidence_refs")
        if d.get("opportunity_ref"):
            _check_refs([d["opportunity_ref"]], known.get("opportunities", set()), f"{p}.opportunity_ref")
        if len(d.get("key_features") or []) > 50 or len(d.get("risks") or []) > 50:
            _fail(p, "key_features/risks ≤50 items")
    for i, b in enumerate(bundle.get("businesses") or []):
        p = f"businesses[{i}]"
        _check_len(b, "name", 300, p, required=True)
        if b.get("website") and (len(b["website"]) > 500 or not b["website"].startswith(("http://", "https://"))):
            _fail(f"{p}.website", "http(s) URL ≤500")
        cc = (b.get("address") or {}).get("country_code") or ""
        if len(cc) > 2:
            _fail(f"{p}.address.country_code", "ISO-2")
        _check_refs(b.get("evidence_refs", []), ev, f"{p}.evidence_refs")
    for i, lead in enumerate(bundle.get("leads") or []):
        p = f"leads[{i}]"
        if bool(lead.get("business_ref")) == bool(lead.get("business_id")):
            _fail(p, "exactly one of business_ref / business_id")
        if lead.get("business_ref"):
            _check_refs([lead["business_ref"]], known.get("businesses", set()), f"{p}.business_ref")
        if lead.get("status", "NEW") not in LEAD_STATUSES:
            _fail(f"{p}.status", "NEW|QUALIFIED|DISQUALIFIED")
        contact = lead.get("contact") or {}
        if contact.get("email_type", "UNKNOWN") not in EMAIL_TYPES:
            _fail(f"{p}.contact.email_type", "invalid")
        if contact.get("legal_basis", "UNKNOWN") not in LEGAL_BASES:
            _fail(f"{p}.contact.legal_basis", "invalid")
        _check_refs(lead.get("evidence_refs", []), ev, f"{p}.evidence_refs")
    for i, c in enumerate(bundle.get("campaigns") or []):
        p = f"campaigns[{i}]"
        _check_len(c, "name", 300, p, required=True)
        if c.get("channel", "EMAIL") != "EMAIL":
            _fail(f"{p}.channel", "EMAIL only in v1")
        if c.get("project_brief_ref") or c.get("project_brief_id"):
            _fail(p, "project_brief is only valid for LOCAL_LEAD_DISCOVERY")
        for j, m in enumerate(c.get("messages") or []):
            mp = f"{p}.messages[{j}]"
            if bool(m.get("lead_ref")) == bool(m.get("lead_id")):
                _fail(mp, "exactly one of lead_ref / lead_id")
            if m.get("lead_ref"):
                _check_refs([m["lead_ref"]], known.get("leads", set()), f"{mp}.lead_ref")
            _check_len(m, "subject", 300, mp, required=True)
            _check_len(m, "body", 20000, mp, required=True)
            if m.get("sequence_step", 1) != 1:
                _fail(f"{mp}.sequence_step", "must be 1 in v1")


# ---------------------------------------------------------------- submission
def chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)] or [[]]


@dataclass
class BatchSubmitter:
    """Validates and submits bundles through `submit` (TaskContext.submit). Tracks refs + report totals."""
    submit: Callable[[dict], dict]
    task_type: str
    batch_size: int = 100
    known: dict[str, set[str]] = field(default_factory=dict)
    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    skipped: list[dict] = field(default_factory=list)
    refs: dict[str, dict[str, str]] = field(default_factory=dict)
    approvals: list[dict] = field(default_factory=list)
    calls: int = 0

    def send(self, **sections: list[dict]) -> dict | None:
        """Submit one bundle with the given sections (no-op if all empty)."""
        if not any(sections.values()):
            return None
        bundle = new_bundle()
        for k, v in sections.items():
            if k not in bundle:
                raise BundleValidationError(f"unknown section {k}")
            bundle[k] = v
        validate_bundle(bundle, self.task_type, self.known)
        report = self.submit(bundle) or {}
        self.calls += 1
        for k, v in sections.items():
            self.known.setdefault(k, set()).update(it["ref"] for it in v)
        for k, n in (report.get("created") or {}).items():
            self.created[k] = self.created.get(k, 0) + n
        for k, n in (report.get("updated") or {}).items():
            self.updated[k] = self.updated.get(k, 0) + n
        self.skipped += report.get("skipped") or []
        for k, m in (report.get("refs") or {}).items():
            self.refs.setdefault(k, {}).update(m)
        self.approvals += report.get("approvals_requested") or []
        return report

    def send_batched(self, section: str, items: list[dict], *, evidence: list[dict] | None = None) -> None:
        """Evidence first (own batches), then `section` items in batches of `batch_size`."""
        for chunk in chunked(evidence or [], self.batch_size):
            self.send(evidence=chunk)
        for chunk in chunked(items, self.batch_size):
            self.send(**{section: chunk})
