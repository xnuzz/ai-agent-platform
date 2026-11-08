import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("platform_sdk")


class PlatformError(Exception):
    """Non-2xx response. `code` follows the backend error envelope (docs/API_CONTRACTS.md §Errors)."""

    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(f"[{status} {code}] {message}")
        self.status, self.code, self.message, self.details = status, code, message, details or {}


@dataclass
class Task:
    id: str
    workspace_id: str
    agent: str
    task_type: str
    input: dict
    lease_id: str
    attempt: int
    context: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> "Task":
        return cls(id=data["id"], workspace_id=data["workspace_id"], agent=data["agent"],
                   task_type=data["task_type"], input=data["input"], lease_id=data["lease_id"],
                   attempt=data["attempt"], context=data.get("context") or {}, raw=data)


class PlatformClient:
    """Thin HTTP client for /api/v1/agent/*. Thread-safe (shared httpx.Client)."""

    def __init__(self, base_url: str, token: str, *, timeout: float = 30.0, transport=None, max_retries: int = 3):
        if not token:
            raise ValueError("Agent token is required (PLATFORM_AGENT_TOKEN).")
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/api/v1/agent/", timeout=timeout, transport=transport,
            headers={"Authorization": f"Agent {token}", "User-Agent": "platform-sdk/1.0"},
        )
        self.max_retries = max_retries

    @classmethod
    def from_env(cls, **kw) -> "PlatformClient":
        return cls(os.environ["PLATFORM_API_URL"], os.environ["PLATFORM_AGENT_TOKEN"], **kw)

    def close(self):
        self._http.close()

    # ------------------------------------------------------------ transport
    def _request(self, method: str, path: str, *, json=None, lease_id: str | None = None) -> Any:
        headers = {"X-Lease-Id": lease_id} if lease_id else {}
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._http.request(method, path, json=json, headers=headers)
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise
                logger.warning("platform request failed (%s), retrying", exc)
                time.sleep(2 ** attempt)
                continue
            if resp.status_code >= 500 and attempt < self.max_retries:
                time.sleep(2 ** attempt)
                continue
            if resp.status_code >= 400:
                try:
                    err = resp.json().get("error", {})
                except ValueError:
                    err = {}
                raise PlatformError(resp.status_code, err.get("code", "error"), err.get("message", resp.text[:200]),
                                    err.get("details"))
            return resp.json() if resp.content else None
        raise RuntimeError("unreachable")

    # ------------------------------------------------------------ API
    def claim(self, worker_id: str, task_types: list[str] | None = None) -> Task | None:
        body = {"worker_id": worker_id, **({"task_types": task_types} if task_types else {})}
        data = self._request("POST", "tasks/claim/", json=body)
        return Task.from_api(data["task"]) if data and data.get("task") else None

    def get_task(self, task_id: str) -> dict:
        return self._request("GET", f"tasks/{task_id}/")

    def heartbeat(self, task: Task, *, progress: int | None = None, stage: str | None = None,
                  message: str | None = None) -> dict:
        body = {k: v for k, v in {"progress": progress, "stage": stage, "message": message}.items() if v is not None}
        return self._request("POST", f"tasks/{task.id}/heartbeat/", json=body, lease_id=task.lease_id)

    def submit_results(self, task: Task, bundle: dict) -> dict:
        return self._request("POST", f"tasks/{task.id}/results/", json=bundle, lease_id=task.lease_id)

    def complete(self, task: Task, summary: dict | None = None) -> dict:
        return self._request("POST", f"tasks/{task.id}/complete/", json={"summary": summary or {}},
                             lease_id=task.lease_id)

    def fail(self, task: Task, code: str, message: str = "", retryable: bool = False) -> dict:
        return self._request("POST", f"tasks/{task.id}/fail/",
                             json={"code": code, "message": message[:2000], "retryable": retryable},
                             lease_id=task.lease_id)

    def check_suppression(self, task: Task, emails=(), phones=()) -> dict:
        return self._request("POST", "suppression/check/",
                             json={"task_id": task.id, "emails": list(emails), "phones": list(phones)})
