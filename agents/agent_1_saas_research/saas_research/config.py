"""Runtime configuration, read from environment variables only (no secrets in code).

See README.md §Environment for the full list.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

from .errors import ConfigurationError

DEFAULT_LLM_MODEL = "claude-sonnet-5-5"
LLM_PROVIDERS = ("anthropic", "fake")
SEARCH_PROVIDERS = ("brave", "serpapi", "fake")
FETCHERS = ("http", "fake")
MOCK_PROVIDERS = {"fake"}
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise ConfigurationError(f"Invalid boolean value: {value!r}")


def _int(env: Mapping[str, str], key: str, default: int, lo: int, hi: int) -> int:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        val = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an integer, got {raw!r}") from exc
    if not lo <= val <= hi:
        raise ConfigurationError(f"{key} must be between {lo} and {hi}, got {val}")
    return val


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        val = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be a number, got {raw!r}") from exc
    if val <= 0:
        raise ConfigurationError(f"{key} must be > 0")
    return val


def _choice(env: Mapping[str, str], key: str, default: str, choices: tuple[str, ...]) -> str:
    val = (env.get(key) or default).strip().lower()
    if val not in choices:
        raise ConfigurationError(f"{key} must be one of {', '.join(choices)}; got {val!r}")
    return val


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_provider: str = "anthropic"
    llm_model: str = DEFAULT_LLM_MODEL
    llm_api_key: str | None = field(default=None, repr=False)
    llm_max_tokens: int = 16000
    llm_effort: str | None = None
    llm_fallbacks: bool = True
    llm_timeout: float = 300.0
    llm_max_retries: int = 2
    # Search / fetch
    search_provider: str = "brave"
    search_api_key: str | None = field(default=None, repr=False)
    search_results_per_query: int = 8
    search_timeout: float = 20.0
    fetcher: str = "http"
    fetch_timeout: float = 15.0
    fetch_max_bytes: int = 1_500_000
    fetch_respect_robots: bool = True
    user_agent: str = "SaaSResearchAgent/1.0 (+B2B research bot)"
    # Pipeline
    batch_size: int = 100
    idea_approval_min_score: int = 60
    lead_min_fit_score: int = 50
    # Worker
    worker_id: str | None = None
    poll_interval: float = 5.0
    heartbeat_interval: float = 60.0
    allow_mock_providers: bool = False

    @property
    def uses_mocks(self) -> bool:
        return bool({self.llm_provider, self.search_provider, self.fetcher} & MOCK_PROVIDERS)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        effort = (env.get("LLM_EFFORT") or "").strip().lower() or None
        if effort is not None and effort not in EFFORT_LEVELS:
            raise ConfigurationError(f"LLM_EFFORT must be one of {', '.join(EFFORT_LEVELS)}; got {effort!r}")
        return cls(
            llm_provider=_choice(env, "LLM_PROVIDER", "anthropic", LLM_PROVIDERS),
            llm_model=(env.get("LLM_MODEL") or "").strip() or DEFAULT_LLM_MODEL,
            llm_api_key=(env.get("LLM_API_KEY") or "").strip() or None,
            llm_max_tokens=_int(env, "LLM_MAX_TOKENS", 16000, 1024, 128000),
            llm_effort=effort,
            llm_fallbacks=_bool(env.get("LLM_FALLBACKS"), True),
            llm_timeout=_float(env, "LLM_TIMEOUT_SECONDS", 300.0),
            llm_max_retries=_int(env, "LLM_MAX_RETRIES", 2, 0, 10),
            search_provider=_choice(env, "SEARCH_PROVIDER", "brave", SEARCH_PROVIDERS),
            search_api_key=(env.get("SEARCH_API_KEY") or "").strip() or None,
            search_results_per_query=_int(env, "SEARCH_RESULTS_PER_QUERY", 8, 1, 20),
            search_timeout=_float(env, "SEARCH_TIMEOUT_SECONDS", 20.0),
            fetcher=_choice(env, "FETCHER", "http", FETCHERS),
            fetch_timeout=_float(env, "FETCH_TIMEOUT_SECONDS", 15.0),
            fetch_max_bytes=_int(env, "FETCH_MAX_BYTES", 1_500_000, 10_000, 20_000_000),
            fetch_respect_robots=_bool(env.get("FETCH_RESPECT_ROBOTS"), True),
            user_agent=(env.get("AGENT1_USER_AGENT") or "").strip() or cls.user_agent,
            batch_size=_int(env, "AGENT1_BATCH_SIZE", 100, 1, 500),
            idea_approval_min_score=_int(env, "AGENT1_IDEA_APPROVAL_MIN_SCORE", 60, 0, 100),
            lead_min_fit_score=_int(env, "AGENT1_LEAD_MIN_FIT_SCORE", 50, 0, 100),
            worker_id=(env.get("AGENT1_WORKER_ID") or "").strip() or None,
            poll_interval=_float(env, "AGENT1_POLL_INTERVAL_SECONDS", 5.0),
            heartbeat_interval=_float(env, "AGENT1_HEARTBEAT_INTERVAL_SECONDS", 60.0),
            allow_mock_providers=_bool(env.get("AGENT1_ALLOW_MOCK_PROVIDERS"), False),
        )

    def validate_for_worker(self) -> None:
        """Fail fast before polling: real providers need keys; mocks need an explicit opt-in."""
        if self.uses_mocks and not self.allow_mock_providers:
            raise ConfigurationError(
                "Mock providers (LLM_PROVIDER/SEARCH_PROVIDER/FETCHER=fake) produce synthetic data. "
                "Set AGENT1_ALLOW_MOCK_PROVIDERS=true to run them against a platform (dev/test only).")
        if self.llm_provider != "fake" and not self.llm_api_key:
            raise ConfigurationError("LLM_API_KEY is required for LLM_PROVIDER=%s" % self.llm_provider)
        if self.search_provider != "fake" and not self.search_api_key:
            raise ConfigurationError("SEARCH_API_KEY is required for SEARCH_PROVIDER=%s" % self.search_provider)
