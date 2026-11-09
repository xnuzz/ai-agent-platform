"""Evidence registry: the single place where retrieved sources become citable Evidence items.

The LLM only ever sees short source ids (S1, S2, ...). Anything it cites is resolved here; unknown ids are
dropped, so a claim can only reference a source that was actually retrieved. Only cited evidence is submitted.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .sources.base import Page, SearchResult, classify_source_type, clean_text, is_http_url

EXCERPT_LIMIT = 600


def evidence_ref(url: str, kind: str = "") -> str:
    return "ev-" + hashlib.sha1(f"{kind}|{url}".encode()).hexdigest()[:16]


@dataclass
class EvidenceRecord:
    sid: str  # short id shown to the LLM
    ref: str  # bundle ref
    url: str
    title: str
    source_type: str
    excerpt: str
    retrieved_at: str
    metadata: dict = field(default_factory=dict)

    def to_bundle(self) -> dict:
        return {"ref": self.ref, "url": self.url, "title": self.title[:500], "source_type": self.source_type,
                "excerpt": self.excerpt[:EXCERPT_LIMIT], "retrieved_at": self.retrieved_at,
                "metadata": self.metadata}

    def prompt_view(self, text_limit: int = 700) -> dict:
        return {"id": self.sid, "url": self.url, "title": self.title, "type": self.source_type,
                "excerpt": self.excerpt[:text_limit]}


class EvidenceRegistry:
    def __init__(self, prefix: str = "S"):
        self.prefix = prefix
        self._by_sid: dict[str, EvidenceRecord] = {}
        self._by_ref: dict[str, EvidenceRecord] = {}
        self._cited: dict[str, None] = {}  # ordered set of refs
        self._submitted: set[str] = set()

    def __len__(self) -> int:
        return len(self._by_sid)

    def __iter__(self):
        return iter(self._by_sid.values())

    def _add(self, *, url: str, title: str, excerpt: str, retrieved_at: str, source_type: str, kind: str,
             metadata: dict) -> EvidenceRecord | None:
        if not is_http_url(url):
            return None
        ref = evidence_ref(url, kind)
        if ref in self._by_ref:
            return self._by_ref[ref]
        rec = EvidenceRecord(sid=f"{self.prefix}{len(self._by_sid) + 1}", ref=ref, url=url,
                             title=clean_text(title, 500), source_type=source_type,
                             excerpt=clean_text(excerpt, EXCERPT_LIMIT), retrieved_at=retrieved_at,
                             metadata=metadata)
        self._by_sid[rec.sid] = rec
        self._by_ref[ref] = rec
        return rec

    def add_search_result(self, r: SearchResult) -> EvidenceRecord | None:
        meta = {"provider": r.provider, "query": r.query}
        if r.country_code:
            meta["country_code"] = r.country_code
        if r.published:
            meta["published"] = r.published
        return self._add(url=r.url, title=r.title, excerpt=r.snippet, retrieved_at=r.retrieved_at,
                         source_type=classify_source_type(r.url), kind="search", metadata=meta)

    def add_page(self, page: Page, *, excerpt: str, source_type: str = "WEB_PAGE",
                 metadata: dict | None = None) -> EvidenceRecord | None:
        return self._add(url=page.url, title=page.title, excerpt=excerpt, retrieved_at=page.retrieved_at,
                         source_type=source_type, kind="page", metadata=metadata or {})

    def get(self, sid: str) -> EvidenceRecord | None:
        return self._by_sid.get((sid or "").strip())

    def resolve(self, sids: list[str] | tuple[str, ...]) -> list[EvidenceRecord]:
        """Known records for the given ids (unknown/fabricated ids silently dropped), de-duplicated, in order."""
        out: dict[str, EvidenceRecord] = {}
        for sid in sids:
            rec = self.get(sid)
            if rec is not None:
                out.setdefault(rec.ref, rec)
        return list(out.values())

    def cite(self, records: list[EvidenceRecord]) -> list[str]:
        for r in records:
            self._cited.setdefault(r.ref, None)
        return [r.ref for r in records]

    def pending_bundle_items(self) -> list[dict]:
        """Cited evidence not yet submitted; marks it submitted."""
        items = [self._by_ref[ref].to_bundle() for ref in self._cited if ref not in self._submitted]
        self._submitted.update(i["ref"] for i in items)
        return items

    def prompt_sources(self, limit: int | None = None) -> list[dict]:
        recs = list(self._by_sid.values())
        return [r.prompt_view() for r in (recs[:limit] if limit else recs)]
