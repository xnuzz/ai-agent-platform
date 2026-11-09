import hashlib
import json


def content_hash(payload) -> str:
    """Stable SHA-256 over canonical JSON. Used to pin approved content."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()
