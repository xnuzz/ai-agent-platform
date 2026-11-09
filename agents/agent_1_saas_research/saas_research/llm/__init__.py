"""LLM provider layer. `build_llm(settings)` picks the implementation from LLM_PROVIDER."""
from __future__ import annotations

from ..config import Settings
from ..errors import ConfigurationError
from .base import LLMProvider, extract_input, render_input


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        from .anthropic_provider import AnthropicProvider  # imported lazily: SDK only needed for this provider

        if not settings.llm_api_key:
            raise ConfigurationError("LLM_API_KEY is required for LLM_PROVIDER=anthropic")
        return AnthropicProvider(api_key=settings.llm_api_key, model=settings.llm_model,
                                 max_tokens=settings.llm_max_tokens, effort=settings.llm_effort,
                                 fallbacks=settings.llm_fallbacks, timeout=settings.llm_timeout,
                                 max_retries=settings.llm_max_retries)
    if settings.llm_provider == "fake":
        from .fake_provider import FakeLLMProvider

        return FakeLLMProvider()
    raise ConfigurationError(f"Unknown LLM_PROVIDER {settings.llm_provider!r}")


__all__ = ["LLMProvider", "build_llm", "render_input", "extract_input"]
