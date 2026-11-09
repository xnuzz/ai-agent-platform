"""🧪 MOCK LLM provider - for tests and offline development ONLY (LLM_PROVIDER=fake).

It does not call any model. It parses the FACTS JSON block that writing.py embeds in every prompt and
returns the deterministic template text for the requested task, so the structured-output -> validation
-> bundle path is exercised end-to-end. Can be scripted to return raw payloads or raise, for tests.
"""
from __future__ import annotations

import json

from .base import LLMError, LLMProvider
from .templates import brief_text, outreach_text

FACTS_MARKER = "FACTS (JSON):"


class FakeLLMProvider(LLMProvider):
    name = "fake"
    model = "mock"

    def __init__(self, *, scripted: dict[str, list] | None = None):
        # scripted: {"task": [dict | Exception, ...]} consumed in order before falling back to templates
        self.scripted = {k: list(v) for k, v in (scripted or {}).items()}
        self.calls: list[dict] = []

    def generate_json(self, *, task: str, system: str, prompt: str, schema: dict, max_tokens: int = 8000) -> dict:
        self.calls.append({"task": task, "system": system, "prompt": prompt, "schema": schema})
        queue = self.scripted.get(task)
        if queue:
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        if FACTS_MARKER not in prompt:
            raise LLMError("fake provider: prompt has no FACTS block")
        facts = json.loads(prompt.split(FACTS_MARKER, 1)[1].strip())
        if task == "project_brief":
            return brief_text(facts)
        if task == "outreach_email":
            return outreach_text(facts)
        raise LLMError(f"fake provider: unknown task {task!r}")
