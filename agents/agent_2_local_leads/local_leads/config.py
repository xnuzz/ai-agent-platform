"""Runtime configuration, read from environment variables (README §Environment).

Every knob has a safe default so the worker can start with only PLATFORM_API_URL / PLATFORM_AGENT_TOKEN
plus provider credentials. Empty strings count as "unset" (docker env files often contain `VAR=`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_LLM_MODEL = "claude-sonnet-5-5"
DEFAULT_CRAWLER_INFO_URL = "https://localhost/local-leads-bot"  # replace in production (CRAWLER_INFO_URL)


def _env(name: str, default: str = "", environ=None) -> str:
    value = (environ if environ is not None else os.environ).get(name, "")
    return value.strip() if value and value.strip() else default


def _float(name, default, environ=None) -> float:
    return float(_env(name, str(default), environ))


def _int(name, default, environ=None) -> int:
    return int(_env(name, str(default), environ))


def _bool(name, default, environ=None) -> bool:
    return _env(name, "true" if default else "false", environ).lower() in ("1", "true", "yes", "on")


@dataclass
class CrawlerSettings:
    info_url: str = DEFAULT_CRAWLER_INFO_URL      # shown in the User-Agent so site owners can identify us
    connect_timeout: float = 5.0
    read_timeout: float = 10.0
    max_page_bytes: int = 1_500_000               # bounded download per page
    min_host_interval: float = 1.0                # seconds between requests to the same host
    max_crawl_delay: float = 10.0                 # robots Crawl-delay above this -> homepage only
    max_link_checks: int = 8                      # broken-link sample size (same-host links only)
    concurrency: int = 4                          # websites scanned in parallel (different hosts)
    slow_page_seconds: float = 3.0                # SLOW_PAGE_LOAD threshold (HTML document download)
    ssl_expiry_warning_days: int = 14
    ca_bundle: str = ""                           # custom CA file for TLS verification (tests / corp proxies)
    trust_env: bool = True                        # honour HTTP(S)_PROXY / NO_PROXY

    @property
    def user_agent(self) -> str:
        return f"LocalLeadsBot/0.1 (+{self.info_url})"


@dataclass
class Settings:
    platform_api_url: str = ""
    platform_agent_token: str = ""
    worker_id: str = ""
    poll_interval: float = 5.0
    heartbeat_interval: float = 60.0

    discovery_provider: str = "google_places"     # google_places | osm | fake
    google_places_api_key: str = ""
    osm_overpass_url: str = "https://overpass-api.de/api/interpreter"
    osm_nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    fake_discovery_file: str = ""

    llm_provider: str = "anthropic"               # anthropic | fake | template
    llm_model: str = DEFAULT_LLM_MODEL
    llm_api_key: str = ""
    llm_effort: str = "medium"
    llm_timeout: float = 120.0
    llm_max_retries: int = 2
    llm_server_fallback: bool = True              # Anthropic server-side refusal fallback ("default" routing)

    batch_size: int = 10
    hourly_rate: float = 60.0
    currency: str = ""                            # "" -> derived from country (see briefs.currency_for)
    crawler: CrawlerSettings = field(default_factory=CrawlerSettings)

    @classmethod
    def from_env(cls, environ=None) -> "Settings":
        e = environ
        return cls(
            platform_api_url=_env("PLATFORM_API_URL", "", e),
            platform_agent_token=_env("PLATFORM_AGENT_TOKEN", "", e),
            worker_id=_env("WORKER_ID", "", e),
            poll_interval=_float("POLL_INTERVAL", 5.0, e),
            heartbeat_interval=_float("HEARTBEAT_INTERVAL", 60.0, e),
            discovery_provider=_env("DISCOVERY_PROVIDER", "google_places", e).lower(),
            google_places_api_key=_env("GOOGLE_PLACES_API_KEY", "", e),
            osm_overpass_url=_env("OSM_OVERPASS_URL", cls.osm_overpass_url, e),
            osm_nominatim_url=_env("OSM_NOMINATIM_URL", cls.osm_nominatim_url, e),
            fake_discovery_file=_env("FAKE_DISCOVERY_FILE", "", e),
            llm_provider=_env("LLM_PROVIDER", "anthropic", e).lower(),
            llm_model=_env("LLM_MODEL", DEFAULT_LLM_MODEL, e),
            llm_api_key=_env("LLM_API_KEY", "", e),
            llm_effort=_env("LLM_EFFORT", "medium", e).lower(),
            llm_timeout=_float("LLM_TIMEOUT", 120.0, e),
            llm_max_retries=_int("LLM_MAX_RETRIES", 2, e),
            llm_server_fallback=_bool("LLM_SERVER_FALLBACK", True, e),
            batch_size=max(1, _int("BATCH_SIZE", 10, e)),
            hourly_rate=_float("BRIEF_HOURLY_RATE", 60.0, e),
            currency=_env("BRIEF_CURRENCY", "", e).upper(),
            crawler=CrawlerSettings(
                info_url=_env("CRAWLER_INFO_URL", DEFAULT_CRAWLER_INFO_URL, e),
                connect_timeout=_float("CRAWLER_CONNECT_TIMEOUT", 5.0, e),
                read_timeout=_float("CRAWLER_READ_TIMEOUT", 10.0, e),
                max_page_bytes=_int("CRAWLER_MAX_PAGE_BYTES", 1_500_000, e),
                min_host_interval=_float("CRAWLER_MIN_HOST_INTERVAL", 1.0, e),
                max_crawl_delay=_float("CRAWLER_MAX_CRAWL_DELAY", 10.0, e),
                max_link_checks=_int("CRAWLER_MAX_LINK_CHECKS", 8, e),
                concurrency=max(1, _int("CRAWLER_CONCURRENCY", 4, e)),
                slow_page_seconds=_float("CRAWLER_SLOW_PAGE_SECONDS", 3.0, e),
                ssl_expiry_warning_days=_int("CRAWLER_SSL_EXPIRY_WARNING_DAYS", 14, e),
                ca_bundle=_env("CRAWLER_CA_BUNDLE", "", e),
                trust_env=_bool("CRAWLER_TRUST_ENV", True, e),
            ),
        )
