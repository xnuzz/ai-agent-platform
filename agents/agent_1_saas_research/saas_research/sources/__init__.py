"""Research sources. `build_search` / `build_fetcher` pick implementations from SEARCH_PROVIDER / FETCHER."""
from __future__ import annotations

from ..config import Settings
from ..errors import ConfigurationError
from .base import Page, PageFetcher, SearchProvider, SearchResult


def build_search(settings: Settings) -> SearchProvider:
    if settings.search_provider in ("brave", "serpapi"):
        from .search_http import BraveSearch, SerpApiSearch

        if not settings.search_api_key:
            raise ConfigurationError(f"SEARCH_API_KEY is required for SEARCH_PROVIDER={settings.search_provider}")
        cls = BraveSearch if settings.search_provider == "brave" else SerpApiSearch
        return cls(settings.search_api_key, timeout=settings.search_timeout, user_agent=settings.user_agent)
    if settings.search_provider == "fake":
        from .fake import FakeSearchProvider

        return FakeSearchProvider()
    raise ConfigurationError(f"Unknown SEARCH_PROVIDER {settings.search_provider!r}")


def build_fetcher(settings: Settings) -> PageFetcher:
    if settings.fetcher == "http":
        from .fetcher import HttpPageFetcher

        return HttpPageFetcher(timeout=settings.fetch_timeout, max_bytes=settings.fetch_max_bytes,
                               respect_robots=settings.fetch_respect_robots, user_agent=settings.user_agent)
    if settings.fetcher == "fake":
        from .fake import FakePageFetcher

        return FakePageFetcher()
    raise ConfigurationError(f"Unknown FETCHER {settings.fetcher!r}")


__all__ = ["Page", "PageFetcher", "SearchProvider", "SearchResult", "build_search", "build_fetcher"]
