"""Exception hierarchy for Agent 1.

Mapping to the platform (docs/AGENT_1_CONTRACT.md §Failure codes) is done by `platform_sdk.AgentWorker`:
- `ProviderTransientError` subclasses `platform_sdk.RetryableError` -> `fail(code="retryable_error", retryable=True)`
  (rate limits, provider outages, timeouts). The backend re-queues the task while attempts remain.
- Everything else -> `fail(code="agent_error")`.
"""
from platform_sdk import RetryableError


class Agent1Error(Exception):
    """Base class for all Agent 1 errors."""


class ConfigurationError(Agent1Error):
    """Missing/invalid configuration (env vars, unknown provider). Not retryable."""


class ProviderTransientError(RetryableError, Agent1Error):
    """Rate limit, overload, 5xx, network failure or timeout at an external provider. Retryable."""


class ProviderError(Agent1Error):
    """Non-retryable provider failure (bad request, authentication, permission)."""


class LLMOutputError(ProviderError):
    """The model returned output that does not satisfy the requested schema (or was truncated)."""


class LLMRefusalError(ProviderError):
    """The model declined the request (stop_reason == "refusal")."""


class InvalidTaskInput(Agent1Error):
    """The task cannot be acted on (e.g. customer research without an approved idea in task.context).

    The SDK currently reports this as `agent_error`; see INTEGRATION_STATUS "Requests to Team 3" for the
    `invalid_input` mapping request.
    """
