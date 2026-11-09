"""Website technical analysis (real HTTP checks; see website.WebsiteAnalyzer)."""
from .fetcher import FetchResult, PoliteFetcher
from .website import ScanResult, WebsiteAnalyzer, normalize_url

__all__ = ["FetchResult", "PoliteFetcher", "ScanResult", "WebsiteAnalyzer", "normalize_url"]
