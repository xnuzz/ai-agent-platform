"""Test doubles for platform_sdk.TaskContext (unit tests that do not need a live backend)."""
from __future__ import annotations

from dataclasses import dataclass, field

from platform_sdk import TaskCancelled


@dataclass
class FakeTask:
    task_type: str
    input: dict
    context: dict = field(default_factory=dict)
    id: str = "00000000-0000-0000-0000-000000000001"


class FakeCtx:
    """Records progress/submissions; mimics TaskContext semantics incl. cancellation."""

    def __init__(self, task_type: str, input: dict, context: dict | None = None, *, suppressed=(),
                 cancel_at_stage: str | None = None):
        self.task = FakeTask(task_type, input, context or {})
        self.progress_calls: list[tuple] = []
        self.bundles: list[dict] = []
        self.suppression_checks: list[list[str]] = []
        self.suppressed = {s.lower() for s in suppressed}
        self.cancel_at_stage = cancel_at_stage
        self.cancel_requested = False

    @property
    def input(self) -> dict:
        return self.task.input

    @property
    def stages(self) -> list[str]:
        return [c[1] for c in self.progress_calls]

    def progress(self, progress=None, stage=None, message=None):
        assert progress is None or 0 <= progress <= 100
        assert stage is None or len(stage) <= 60
        assert message is None or len(message) <= 500
        self.progress_calls.append((progress, stage, message))
        if self.cancel_at_stage and stage == self.cancel_at_stage:
            self.cancel_requested = True
        if self.cancel_requested:
            raise TaskCancelled()

    def submit(self, bundle: dict) -> dict:
        if self.cancel_requested:
            raise TaskCancelled()
        self.bundles.append(bundle)
        created = {k: len(v) for k, v in bundle.items() if isinstance(v, list) and v}
        approvals = []
        for sec, tt in (("software_ideas", "SOFTWARE_IDEA"), ("campaigns", "CAMPAIGN")):
            approvals += [{"target_type": tt, "status": "PENDING"} for it in bundle.get(sec, [])
                          if it.get("submit_for_approval")]
        return {"created": created, "updated": {}, "skipped": [], "refs": {}, "approvals_requested": approvals}

    def check_suppression(self, emails=(), phones=()):
        self.suppression_checks.append(list(emails))
        return {"suppressed_emails": [e for e in emails if e.lower() in self.suppressed], "suppressed_phones": []}

    def section(self, name: str) -> list[dict]:
        return [it for b in self.bundles for it in b.get(name, [])]
