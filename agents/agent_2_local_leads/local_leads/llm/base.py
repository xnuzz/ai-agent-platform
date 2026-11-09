"""LLM provider interface + minimal JSON-schema validation of structured output.

Providers return a parsed JSON object for a given JSON schema. Callers (writing.py) validate the result
again with `validate()` and fall back to deterministic templates on any error, so a provider outage never
fails a task - it only changes who wrote the prose (recorded in the bundle for the reviewer).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Provider returned no usable output (bad config, invalid JSON, truncated, ...)."""


class LLMUnavailable(LLMError):
    """Transient: rate limit, overload, network, timeout (after the SDK's own retries)."""


class LLMRefusal(LLMError):
    """The model declined the request (stop_reason == "refusal")."""


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def generate_json(self, *, task: str, system: str, prompt: str, schema: dict, max_tokens: int = 8000) -> dict:
        """Return a JSON object conforming to `schema`. `task` is a short label (logging / fakes)."""

    def describe(self) -> str:
        return f"{self.name}:{self.model}" if self.model else self.name


_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}


def validate(data, schema: dict, path: str = "$") -> list[str]:
    """Validate the subset of JSON Schema we use (type, properties, required, additionalProperties, items,
    maxLength, maxItems). Returns a list of error strings (empty = valid)."""
    errors: list[str] = []
    typ = schema.get("type")
    if typ and not (isinstance(data, _TYPES[typ]) and not (typ in ("integer", "number") and isinstance(data, bool))):
        return [f"{path}: expected {typ}"]
    if typ == "object":
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}.{key}: required")
        if schema.get("additionalProperties") is False:
            errors += [f"{path}.{k}: unexpected property" for k in data if k not in props]
        for k, sub in props.items():
            if k in data:
                errors += validate(data[k], sub, f"{path}.{k}")
    elif typ == "array":
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        for i, item in enumerate(data):
            errors += validate(item, schema.get("items", {}), f"{path}[{i}]")
    elif typ == "string":
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']} characters")
        if schema.get("minLength") and len(data.strip()) < schema["minLength"]:
            errors.append(f"{path}: too short")
    return errors


def wire_schema(schema: dict) -> dict:
    """Schema sent to the provider: drop length keywords (enforced locally by `validate`) so providers with a
    restricted JSON-schema dialect accept it."""
    out = {k: v for k, v in schema.items() if k not in ("maxLength", "minLength", "maxItems")}
    if "properties" in out:
        out["properties"] = {k: wire_schema(v) for k, v in out["properties"].items()}
    if isinstance(out.get("items"), dict):
        out["items"] = wire_schema(out["items"])
    return out
