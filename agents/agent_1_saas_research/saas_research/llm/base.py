"""Provider-neutral LLM interface.

Every pipeline step asks for *structured* output: a pydantic model class. Implementations must return a
validated instance of that class or raise one of the errors in `saas_research.errors`:
`ProviderTransientError` (retryable), `LLMOutputError`, `LLMRefusalError`, `ProviderError`.
"""
from __future__ import annotations

import json
import re
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

INPUT_OPEN, INPUT_CLOSE = "<input>", "</input>"
_INPUT_RE = re.compile(re.escape(INPUT_OPEN) + r"\s*(\{.*\})\s*" + re.escape(INPUT_CLOSE), re.S)


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, *, system: str, prompt: str, output_model: type[T], max_tokens: int | None = None) -> T:
        """Return a validated `output_model` instance."""
        ...


def render_input(data: dict[str, Any]) -> str:
    """Embed the step's structured input in the prompt. Sorted keys keep prompts byte-stable (cache-friendly)."""
    return f"{INPUT_OPEN}\n{json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1)}\n{INPUT_CLOSE}"


def extract_input(prompt: str) -> dict[str, Any]:
    """Inverse of `render_input` (used by the fake provider and tests)."""
    m = _INPUT_RE.search(prompt)
    return json.loads(m.group(1)) if m else {}
