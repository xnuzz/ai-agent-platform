"""🧪 MOCK search provider + page fetcher — deterministic, offline, for tests and local dev ONLY.

Every URL it returns lives under reserved test domains (`*.example.com`, `*.example.test`, RFC 2606) so mock data can
never be mistaken for real evidence. Selected with SEARCH_PROVIDER=fake / FETCHER=fake; the CLI refuses to run mocks
unless AGENT1_ALLOW_MOCK_PROVIDERS=true.
"""
from __future__ import annotations

import hashlib
import re

from .base import Page, SearchResult, domain_of, utcnow_iso

MOCK_MARKER = "[MOCK]"


def _slug(text: str, n: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n] or "q"


def _h(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)


def is_mock_business_url(url: str) -> bool:
    return domain_of(url).startswith("biz-") and domain_of(url).endswith(".example.test")


class FakeSearchProvider:
    """🧪 Mock. For each query returns: 1 forum thread, 1 review page, then business websites (biz-*.example.test)."""

    name = "fake"

    def __init__(self, businesses_per_query: int = 3):
        self.businesses_per_query = businesses_per_query
        self.calls: list[dict] = []

    def search(self, query: str, *, max_results: int, country: str | None = None,
               language: str | None = None) -> list[SearchResult]:
        self.calls.append({"query": query, "max_results": max_results, "country": country, "language": language})
        s, now, cc = _slug(query), utcnow_iso(), (country or "").upper()
        results = [
            SearchResult(url=f"https://forum.example.com/t/{s}", title=f"{MOCK_MARKER} Forum: {query}",
                         snippet=f"{MOCK_MARKER} 'We still do {query} by hand in spreadsheets, it costs us hours "
                                 f"every week.'", retrieved_at=now, provider=self.name, query=query, country_code=cc),
            SearchResult(url=f"https://reviews.example.com/{s}", title=f"{MOCK_MARKER} Reviews: {query} tools",
                         snippet=f"{MOCK_MARKER} 'The leading tool (MockSuite) is too expensive for small teams.'",
                         retrieved_at=now, provider=self.name, query=query, country_code=cc),
        ]
        for i in range(self.businesses_per_query):
            dom = f"biz-{_slug(query, 20)}-{(cc or 'xx').lower()}-{i + 1}.example.test"
            results.append(SearchResult(
                url=f"https://www.{dom}/", title=f"{MOCK_MARKER} Mock Business {i + 1} ({cc or 'global'})",
                snippet=f"{MOCK_MARKER} Family-run business in Mocktown. Contact us for appointments.",
                retrieved_at=now, provider=self.name, query=query, country_code=cc))
        return results[:max_results]


class FakePageFetcher:
    """🧪 Mock. Business pages expose a generic info@ address; every 4th exposes only a personal-looking address,
    every 5th none at all, and pages also mention a third-party address (filtered by the pipeline)."""

    name = "fake"

    def __init__(self):
        self.calls: list[str] = []

    def fetch(self, url: str) -> Page | None:
        self.calls.append(url)
        dom = domain_of(url)
        if not is_mock_business_url(url):
            return Page(url=url, status=200, title=f"{MOCK_MARKER} {dom}", text=f"{MOCK_MARKER} page {url}",
                        retrieved_at=utcnow_iso())
        k = _h(dom) % 20
        if k % 5 == 4:
            emails: tuple[str, ...] = ()
        elif k % 4 == 3:
            emails = (f"jane.doe@{dom}",)
        else:
            emails = (f"info@{dom}",)
        emails = emails + ("support@webbuilder.example.com",)
        text = (f"{MOCK_MARKER} Welcome to Mock Business in Mocktown. Contact: {', '.join(emails)}. "
                f"Site built with WebBuilder.")
        return Page(url=url, status=200, title=f"{MOCK_MARKER} {dom}", text=text, retrieved_at=utcnow_iso(),
                    emails=emails)
