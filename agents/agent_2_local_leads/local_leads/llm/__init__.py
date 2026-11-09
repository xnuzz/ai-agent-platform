"""LLM provider layer. Select with LLM_PROVIDER = anthropic (default) | fake (🧪 mock) | template (no LLM)."""
from __future__ import annotations

import logging

from .base import LLMError, LLMProvider, LLMRefusal, LLMUnavailable, validate

logger = logging.getLogger("local_leads.llm")

__all__ = ["LLMError", "LLMProvider", "LLMRefusal", "LLMUnavailable", "validate", "build_llm"]


def build_llm(settings) -> LLMProvider | None:
    """Return the configured provider, or None for template-only writing."""
    name = settings.llm_provider
    if name in ("template", "templates", "none"):
        return None
    if name == "fake":
        from .fake import FakeLLMProvider

        logger.warning("LLM_PROVIDER=fake: using the MOCK LLM provider (deterministic templates, no model calls)")
        return FakeLLMProvider()
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        try:
            return AnthropicProvider(model=settings.llm_model, api_key=settings.llm_api_key,
                                     effort=settings.llm_effort, timeout=settings.llm_timeout,
                                     max_retries=settings.llm_max_retries,
                                     server_fallback=settings.llm_server_fallback)
        except Exception as exc:  # noqa: BLE001 - e.g. missing credentials: degrade to templates, loudly
            logger.error("Anthropic provider unavailable (%s); briefs/outreach will use templates", exc)
            return None
    raise ValueError(f"Unknown LLM_PROVIDER {name!r} (expected anthropic | fake | template)")
