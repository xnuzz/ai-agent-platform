"""Research source interfaces: web search + page fetching.

Everything a source returns is *retrieved* data (real URL, retrieval timestamp, verbatim snippet/text), so it can
become citable Evidence. Providers must never synthesize URLs.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: str | None, limit: int | None = None) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    text = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value or ""))).strip()
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def is_http_url(url: str | None, max_length: int = 2000) -> bool:
    if not url or len(url) > max_length:
        return False
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc) and " " not in url


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def origin_of(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str
    retrieved_at: str
    provider: str
    query: str = ""
    country_code: str = ""
    published: str = ""


@dataclass(frozen=True)
class Page:
    url: str  # final URL after redirects
    status: int
    title: str
    text: str
    retrieved_at: str
    emails: tuple[str, ...] = field(default_factory=tuple)


@runtime_checkable
class SearchProvider(Protocol):
    name: str

    def search(self, query: str, *, max_results: int, country: str | None = None,
               language: str | None = None) -> list[SearchResult]:
        """Return up to `max_results` real results. Raise ProviderTransientError on rate limits/outages."""
        ...


@runtime_checkable
class PageFetcher(Protocol):
    name: str

    def fetch(self, url: str) -> Page | None:
        """Fetch one page; None if unavailable, disallowed by robots.txt, or not HTML/text."""
        ...


# Domain -> Evidence source_type (backend enum EvidenceSourceType)
_FORUM = ("reddit.com", "news.ycombinator.com", "quora.com", "stackexchange.com", "stackoverflow.com",
          "community.", "forum.", "forums.", "discourse.")
_REVIEW = ("g2.com", "capterra.", "trustpilot.com", "getapp.", "softwareadvice.com", "trustradius.com",
           "producthunt.com", "reviews.", "yelp.")
_SOCIAL = ("twitter.com", "x.com", "linkedin.com", "facebook.com", "instagram.com", "youtube.com", "tiktok.com",
           "mastodon.")
_DIRECTORY = ("maps.google.", "yellowpages.", "gelbeseiten.", "europages.", "crunchbase.com", "directory.",
              "clutch.co", "yelp.")


def classify_source_type(url: str) -> str:
    d = domain_of(url)

    def hit(patterns):
        return any(d == p or d.endswith("." + p) or (p.endswith(".") and (d.startswith(p) or f".{p}" in d))
                   for p in patterns)

    if hit(_FORUM):
        return "FORUM"
    if hit(_REVIEW):
        return "REVIEW"
    if hit(_SOCIAL):
        return "SOCIAL"
    if hit(_DIRECTORY):
        return "DIRECTORY"
    return "WEB_PAGE"
