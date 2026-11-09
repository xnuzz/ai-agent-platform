"""Wiring: Settings -> providers -> handlers -> platform_sdk.AgentWorker."""
from __future__ import annotations

import logging

from platform_sdk import AgentWorker, PlatformClient

from .config import Settings
from .errors import ConfigurationError
from .handlers import Agent1Handlers, PipelineOptions, Providers
from .llm import build_llm
from .sources import build_fetcher, build_search

logger = logging.getLogger("saas_research.worker")


def build_providers(settings: Settings) -> Providers:
    return Providers(llm=build_llm(settings), search=build_search(settings), fetcher=build_fetcher(settings))


def build_handlers(settings: Settings, providers: Providers | None = None) -> dict:
    return Agent1Handlers(providers or build_providers(settings), PipelineOptions.from_settings(settings)).as_dict()


def build_worker(settings: Settings, client: PlatformClient | None = None) -> AgentWorker:
    """Validate config and build the worker. Without `client`, uses PLATFORM_API_URL / PLATFORM_AGENT_TOKEN."""
    settings.validate_for_worker()
    if client is None:
        try:
            client = PlatformClient.from_env()
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("PLATFORM_API_URL and PLATFORM_AGENT_TOKEN are required") from exc
    if settings.uses_mocks:
        logger.warning("RUNNING WITH MOCK PROVIDERS (llm=%s search=%s fetcher=%s): output is synthetic test data",
                       settings.llm_provider, settings.search_provider, settings.fetcher)
    return AgentWorker(client, build_handlers(settings), worker_id=settings.worker_id,
                       poll_interval=settings.poll_interval, heartbeat_interval=settings.heartbeat_interval)
