"""Real web-search providers over HTTP (httpx). Selected with SEARCH_PROVIDER, key from SEARCH_API_KEY.

- `brave`   — Brave Search Web API  (GET https://api.search.brave.com/res/v1/web/search)
- `serpapi` — SerpAPI Google engine (GET https://serpapi.com/search.json)

Neither can be exercised in this repository's CI (no keys); they are unit-tested with httpx.MockTransport.
"""
from __future__ import annotations

import logging

import httpx

from ..errors import ProviderError, ProviderTransientError
from .base import SearchResult, clean_text, is_http_url, utcnow_iso

logger = logging.getLogger("saas_research.sources.search")


class _HTTPSearch:
    name = "base"
    base_url = ""

    def __init__(self, api_key: str, *, timeout: float = 20.0, transport: httpx.BaseTransport | None = None,
                 user_agent: str = "SaaSResearchAgent/1.0"):
        if not api_key:
            raise ProviderError(f"{self.name} search requires SEARCH_API_KEY.")
        self._api_key = api_key
        self._http = httpx.Client(timeout=timeout, transport=transport, headers={"User-Agent": user_agent,
                                                                                 "Accept": "application/json"})

    def close(self) -> None:
        self._http.close()

    def _get(self, params: dict, headers: dict | None = None) -> dict:
        try:
            resp = self._http.get(self.base_url, params=params, headers=headers or {})
        except httpx.TransportError as exc:  # connect/read errors and timeouts
            raise ProviderTransientError(f"{self.name} search unreachable: {exc}") from exc
        if resp.status_code == 429 or resp.status_code >= 500:
            raise ProviderTransientError(f"{self.name} search unavailable (HTTP {resp.status_code}).")
        if resp.status_code >= 400:
            raise ProviderError(f"{self.name} search rejected the request (HTTP {resp.status_code}).")
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderTransientError(f"{self.name} search returned non-JSON response.") from exc


class BraveSearch(_HTTPSearch):
    name = "brave"
    base_url = "https://api.search.brave.com/res/v1/web/search"

    def search(self, query: str, *, max_results: int, country: str | None = None,
               language: str | None = None) -> list[SearchResult]:
        params: dict = {"q": query, "count": max(1, min(max_results, 20))}
        if country:
            params["country"] = country.upper()
        if language:
            params["search_lang"] = language.lower()
        data = self._get(params, headers={"X-Subscription-Token": self._api_key})
        now, out = utcnow_iso(), []
        for item in (data.get("web") or {}).get("results") or []:
            url = item.get("url") or ""
            if not is_http_url(url):
                continue
            snippet = " ".join([item.get("description") or "", *(item.get("extra_snippets") or [])[:2]])
            out.append(SearchResult(url=url, title=clean_text(item.get("title"), 500),
                                    snippet=clean_text(snippet, 1200), retrieved_at=now, provider=self.name,
                                    query=query, country_code=(country or "").upper(),
                                    published=str(item.get("page_age") or item.get("age") or "")))
        return out[:max_results]


class SerpApiSearch(_HTTPSearch):
    name = "serpapi"
    base_url = "https://serpapi.com/search.json"

    def search(self, query: str, *, max_results: int, country: str | None = None,
               language: str | None = None) -> list[SearchResult]:
        params: dict = {"engine": "google", "q": query, "num": max(1, min(max_results, 20)),
                        "api_key": self._api_key}
        if country:
            params["gl"] = country.lower()
        if language:
            params["hl"] = language.lower()
        data = self._get(params)
        if data.get("error") and not data.get("organic_results"):
            # SerpAPI reports "no results" as an error string with HTTP 200.
            logger.info("serpapi: %s", data.get("error"))
            return []
        now, out = utcnow_iso(), []
        for item in data.get("organic_results") or []:
            url = item.get("link") or ""
            if not is_http_url(url):
                continue
            out.append(SearchResult(url=url, title=clean_text(item.get("title"), 500),
                                    snippet=clean_text(item.get("snippet"), 1200), retrieved_at=now,
                                    provider=self.name, query=query, country_code=(country or "").upper(),
                                    published=str(item.get("date") or "")))
        return out[:max_results]
