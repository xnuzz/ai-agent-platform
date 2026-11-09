"""Anthropic (Claude) implementation of `LLMProvider` — the default provider.

- Structured output via `client.beta.messages.parse(output_format=<pydantic model>)` (JSON-schema constrained,
  SDK-validated), re-validated here.
- Server-side refusal fallback (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`) is ON by default;
  disable with LLM_FALLBACKS=false (e.g. on platforms that do not support it).
- Error mapping: 429 / 5xx / 529 overloaded / connection errors / timeouts -> ProviderTransientError
  (a platform_sdk.RetryableError, so the task is re-queued); 4xx -> ProviderError; refusal -> LLMRefusalError;
  schema violation or truncation -> LLMOutputError.
- The API key comes only from configuration (env LLM_API_KEY); nothing is hard-coded.
"""
from __future__ import annotations

import logging
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from ..config import DEFAULT_LLM_MODEL
from ..errors import LLMOutputError, LLMRefusalError, ProviderError, ProviderTransientError
from .base import T

logger = logging.getLogger("saas_research.llm.anthropic")

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str | None, model: str = DEFAULT_LLM_MODEL, max_tokens: int = 16000,
                 effort: str | None = None, fallbacks: bool = True, timeout: float = 300.0, max_retries: int = 2,
                 output_retries: int = 1, client: anthropic.Anthropic | None = None, http_client: Any = None):
        if client is None:
            if not api_key:
                raise ProviderError("Anthropic provider requires an API key (LLM_API_KEY).")
            kw: dict[str, Any] = {"api_key": api_key, "timeout": timeout, "max_retries": max_retries}
            if http_client is not None:
                kw["http_client"] = http_client
            client = anthropic.Anthropic(**kw)
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self.fallbacks = fallbacks
        self.output_retries = output_retries

    def _request_kwargs(self, system: str, prompt: str, output_model: type[BaseModel], max_tokens: int | None):
        kw: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "output_format": output_model,
        }
        if self.effort:
            kw["output_config"] = {"effort": self.effort}
        if self.fallbacks:
            kw["betas"] = [FALLBACK_BETA]
            kw["fallbacks"] = "default"
        return kw

    def generate(self, *, system: str, prompt: str, output_model: type[T], max_tokens: int | None = None) -> T:
        kwargs = self._request_kwargs(system, prompt, output_model, max_tokens)
        last_error: Exception | None = None
        for attempt in range(self.output_retries + 1):
            try:
                response = self.client.beta.messages.parse(**kwargs)
            except anthropic.RateLimitError as exc:
                raise ProviderTransientError(f"Anthropic rate limit: {exc.message}") from exc
            except anthropic.APIStatusError as exc:
                if exc.status_code >= 500 or exc.status_code in (408, 409):
                    raise ProviderTransientError(f"Anthropic unavailable ({exc.status_code}): {exc.message}") from exc
                raise ProviderError(f"Anthropic request failed ({exc.status_code}): {exc.message}") from exc
            except anthropic.APIConnectionError as exc:  # includes APITimeoutError
                raise ProviderTransientError(f"Anthropic connection error: {exc}") from exc
            except ValidationError as exc:  # SDK-side parse of the JSON against output_model
                last_error = LLMOutputError(f"Model output failed schema validation: {exc.error_count()} error(s)")
                logger.warning("structured output invalid (attempt %s): %s", attempt + 1, exc)
                continue
            except ValueError as exc:  # malformed JSON text
                last_error = LLMOutputError(f"Model output was not valid JSON: {exc}")
                logger.warning("structured output not JSON (attempt %s): %s", attempt + 1, exc)
                continue

            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                category = getattr(details, "category", None) if details else None
                raise LLMRefusalError(f"Model declined the request (category={category}).")
            if response.stop_reason == "max_tokens":
                last_error = LLMOutputError("Model output truncated at max_tokens.")
                continue
            parsed = response.parsed_output
            if parsed is None:
                last_error = LLMOutputError("Model returned no structured output.")
                continue
            try:
                return output_model.model_validate(parsed.model_dump() if isinstance(parsed, BaseModel) else parsed)
            except ValidationError as exc:
                last_error = LLMOutputError(f"Model output failed schema validation: {exc.error_count()} error(s)")
                continue
        assert last_error is not None
        raise last_error
