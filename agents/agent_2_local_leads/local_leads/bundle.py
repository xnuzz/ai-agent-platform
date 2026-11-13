"""Result Bundle v1.0 construction (docs/API_CONTRACTS.md §Result Bundle, AGENT_2_CONTRACT.md).

Bundles are atomic on the backend: one invalid field rejects the whole batch. Provider and website data
is therefore sanitised here to the backend's field rules (lengths, URL/e-mail shape, decimal places).
Refs are deterministic per business (`DiscoveredBusiness.key`), so a retried task updates instead of
duplicating.
"""
from __future__ import annotations

import ipaddress
import json
import re
from urllib.parse import urlsplit

from platform_sdk import new_bundle

from .analyzer.website import ScanResult, normalize_url
from .bulgaria import is_social_only
from .contacts import EMAIL_RE
from .models import DiscoveredBusiness, Finding

PROBLEM_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,59}$")
MAX_REF = 200


def clip(value, n: int) -> str:
    s = "" if value is None else str(value).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def clean_url(value: str, max_len: int = 500) -> str:
    """Return a URL the backend's URLField accepts, or "" (never fail a whole batch on one bad URL)."""
    if not value:
        return ""
    url = normalize_url(value)
    p = urlsplit(url)
    host = p.hostname or ""
    if p.scheme not in ("http", "https") or not host or " " in url or len(url) > max_len:
        return ""
    try:
        ipaddress.ip_address(host)
        return url
    except ValueError:
        pass
    if host == "localhost" or re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\.?", host):
        return url
    return ""


def clean_email(value: str) -> str:
    v = (value or "").strip().lower()
    return v if EMAIL_RE.match(v) else ""


def coord(value) -> float | None:
    if value is None:
        return None
    try:
        v = round(float(value), 6)
    except (TypeError, ValueError):
        return None
    return v if abs(v) <= 180 else None


def jsonable(data: dict) -> dict:
    return json.loads(json.dumps(data, default=str))


class Refs:
    def __init__(self, b: DiscoveredBusiness):
        k = b.key
        self.business, self.lead, self.brief, self.campaign = f"biz:{k}", f"lead:{k}", f"brief:{k}", f"camp:{k}"
        self.listing, self.scan = f"ev:{k}:listing", f"ev:{k}:scan"

    def finding(self, code: str, n: int) -> str:
        return f"ev:{self.business[4:]}:{code.lower()}:{n}"


class BatchBundle:
    """Accumulates one batch of businesses (and everything derived from them) as a Result Bundle."""

    def __init__(self):
        self.data = new_bundle()

    def _evidence(self, item: dict) -> str:
        self.data["evidence"].append(item)
        return item["ref"]

    # ------------------------------------------------------------------ evidence
    def listing_evidence(self, b: DiscoveredBusiness, refs: Refs, retrieved_at: str) -> str:
        meta = {"provider": b.provider, **jsonable(b.source_data)}
        if b.attribution:
            meta["attribution"] = b.attribution
        excerpt = "; ".join(x for x in (
            f"Name: {b.name}", f"Category: {b.category}" if b.category else "",
            f"Website: {b.website}" if b.website else "Website: none listed",
            f"Phone: {b.phone}" if b.phone else "",
            f"Address: {', '.join(p for p in (b.address_line1, b.postal_code, b.city, b.country_code) if p)}")
            if x)
        return self._evidence({"ref": refs.listing, "url": clean_url(b.listing_url, 2000),
                               "title": clip(b.listing_title or f"{b.provider} listing: {b.name}", 500),
                               "source_type": "DIRECTORY", "excerpt": clip(excerpt, 5000),
                               "retrieved_at": retrieved_at, "metadata": meta})

    def scan_evidence(self, scan: ScanResult, refs: Refs) -> str:
        return self._evidence({"ref": refs.scan, "url": clean_url(scan.final_url or scan.url, 2000),
                               "title": clip(f"Website scan: {scan.final_url or scan.url}", 500),
                               "source_type": "WEBSITE_SCAN", "excerpt": clip(scan.summary(), 5000),
                               "retrieved_at": scan.retrieved_at,
                               "metadata": jsonable({"facts": scan.facts, "pages": scan.pages,
                                                     "scanned": scan.scanned, "skipped_reason": scan.skipped_reason,
                                                     "scanner": "local_leads.analyzer"})})

    def finding_evidence(self, f: Finding, refs: Refs, n: int, retrieved_at: str) -> str:
        return self._evidence({"ref": refs.finding(f.code, n), "url": clean_url(f.url, 2000),
                               "title": clip(f"{f.code}: {f.title}", 500), "source_type": "WEBSITE_SCAN",
                               "excerpt": clip(f.description, 5000), "retrieved_at": retrieved_at,
                               "metadata": jsonable({"code": f.code, "facts": f.facts})})

    # ------------------------------------------------------------------ entities
    def business(self, b: DiscoveredBusiness, refs: Refs, *, email: str, evidence_refs: list[str]) -> None:
        cc = (b.country_code or "").strip().upper()
        self.data["businesses"].append({
            "ref": refs.business, "name": clip(b.name, 300),
            # a Facebook/marketplace page is not the business's site (backend dedupes businesses by site domain)
            "website": "" if is_social_only(b.website) else clean_url(b.website),
            "email": clean_email(email), "phone": clip(b.phone, 50),
            "address": {"line1": clip(b.address_line1, 300), "city": clip(b.city, 120),
                        "region": clip(b.region, 120), "postal_code": clip(b.postal_code, 20),
                        "country_code": cc if re.fullmatch(r"[A-Z]{2}", cc) else ""},
            "latitude": coord(b.latitude), "longitude": coord(b.longitude), "category": clip(b.category, 200),
            "source_data": jsonable(b.source_data), "evidence_refs": evidence_refs,
        })

    @staticmethod
    def problem(f: Finding, evidence_refs: list[str]) -> dict:
        assert PROBLEM_CODE_RE.match(f.code), f.code
        return {"code": f.code, "title": clip(f.title, 300), "severity": f.severity,
                "description": clip(f.description, 5000), "evidence_refs": evidence_refs}

    def lead(self, refs: Refs, *, status: str, score: int, notes: str, problems: list[dict], contact: dict,
             evidence_refs: list[str]) -> None:
        self.data["leads"].append({"ref": refs.lead, "business_ref": refs.business, "status": status, "score": score,
                                   "qualification_notes": notes, "problems": problems, "contact": contact,
                                   "evidence_refs": evidence_refs})

    def brief(self, refs: Refs, *, text: dict, problems: list[dict], estimate, evidence_refs: list[str],
              submit: bool, approval_summary: str) -> None:
        self.data["project_briefs"].append({
            "ref": refs.brief, "lead_ref": refs.lead, "title": clip(text["title"], 300),
            "summary": clip(text["summary"], 20000), "problems": problems,
            "proposed_solution": text["proposed_solution"],
            "scope_items": [clip(s, 500) for s in estimate.scope_items][:50],
            "tech_stack": [clip(s, 500) for s in estimate.tech_stack][:50],
            "estimated_effort_hours": {"min": estimate.hours_min, "max": estimate.hours_max},
            "estimated_budget": {"min": estimate.budget_min, "max": estimate.budget_max,
                                 "currency": estimate.currency},
            "evidence_refs": evidence_refs, "submit_for_approval": submit,
            "approval_summary": clip(approval_summary, 5000),
        })

    def campaign(self, refs: Refs, *, name: str, offer: dict, subject: str, body: str, language: str,
                 approval_summary: str) -> None:
        self.data["campaigns"].append({
            "ref": refs.campaign, "name": clip(name, 300), "channel": "EMAIL",
            "offer": {"headline": clip(offer.get("headline"), 300),
                      "value_proposition": clip(offer.get("value_proposition"), 5000),
                      "pricing": clip(offer.get("pricing"), 2000),
                      "call_to_action": clip(offer.get("call_to_action"), 500)},
            "project_brief_ref": refs.brief,
            "messages": [{"lead_ref": refs.lead, "subject": clip(subject, 300), "body": body[:20000],
                          "language": clip(language, 10), "sequence_step": 1}],
            "submit_for_approval": True, "approval_summary": clip(approval_summary, 5000),
        })

    def payload(self) -> dict:
        """Bundle with empty sections removed (smaller request; backend defaults them)."""
        return {k: v for k, v in self.data.items() if v or k == "schema_version"}
