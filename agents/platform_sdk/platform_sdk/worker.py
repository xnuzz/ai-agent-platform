import logging
import socket
import threading
import uuid
from typing import Callable

from .client import PlatformClient, PlatformError, Task

logger = logging.getLogger("platform_sdk.worker")
SCHEMA_VERSION = "1.0"


def new_bundle() -> dict:
    """Empty result bundle (docs/API_CONTRACTS.md §Agent result bundle)."""
    return {"schema_version": SCHEMA_VERSION, "evidence": [], "opportunities": [], "software_ideas": [],
            "businesses": [], "leads": [], "project_briefs": [], "campaigns": []}


class TaskCancelled(Exception):
    """Raised inside a handler when the user cancelled the task."""


class RetryableError(Exception):
    """Raise from a handler for transient failures (rate limits, provider outage) -> task is re-queued."""


class TaskContext:
    def __init__(self, client: PlatformClient, task: Task):
        self.client, self.task = client, task
        self.cancel_requested = False

    @property
    def input(self) -> dict:
        return self.task.input

    def progress(self, progress: int | None = None, stage: str | None = None, message: str | None = None) -> None:
        """Report progress + renew lease. Raises TaskCancelled if the user cancelled."""
        resp = self.client.heartbeat(self.task, progress=progress, stage=stage, message=message)
        if resp.get("cancel_requested"):
            self.cancel_requested = True
        self.check_cancelled()

    def check_cancelled(self) -> None:
        if self.cancel_requested:
            raise TaskCancelled()

    def submit(self, bundle: dict) -> dict:
        """Persist results. Returns report incl. `refs` (ref -> backend UUID) and `approvals_requested`."""
        self.check_cancelled()
        return self.client.submit_results(self.task, bundle)

    def check_suppression(self, emails=(), phones=()) -> dict:
        return self.client.check_suppression(self.task, emails, phones)


Handler = Callable[[TaskContext], "dict | None"]


class AgentWorker:
    """Claims tasks for the registered task types and runs the matching handler.

    handlers: {"SAAS_OPPORTUNITY_RESEARCH": fn(ctx) -> summary dict}
    A background thread heartbeats every `heartbeat_interval` seconds so long LLM calls keep the lease.
    """

    def __init__(self, client: PlatformClient, handlers: dict[str, Handler], *, worker_id: str | None = None,
                 poll_interval: float = 5.0, heartbeat_interval: float = 60.0):
        self.client, self.handlers = client, handlers
        self.worker_id = worker_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.poll_interval, self.heartbeat_interval = poll_interval, heartbeat_interval

    def _keepalive(self, ctx: TaskContext, stop: threading.Event):
        while not stop.wait(self.heartbeat_interval):
            try:
                if self.client.heartbeat(ctx.task).get("cancel_requested"):
                    ctx.cancel_requested = True
            except PlatformError as exc:
                logger.warning("heartbeat failed for %s: %s", ctx.task.id, exc)
                if exc.code in ("lease_lost", "task_not_running"):
                    ctx.cancel_requested = True
                    return

    def run_once(self) -> bool:
        task = self.client.claim(self.worker_id, task_types=list(self.handlers))
        if task is None:
            return False
        ctx, stop = TaskContext(self.client, task), threading.Event()
        beat = threading.Thread(target=self._keepalive, args=(ctx, stop), daemon=True)
        beat.start()
        try:
            summary = self.handlers[task.task_type](ctx)
            stop.set()
            self.client.complete(task, summary or {})
        except TaskCancelled:
            stop.set()
            self._safe_fail(task, "CANCELLED", "Cancelled by user.")
        except RetryableError as exc:
            stop.set()
            self._safe_fail(task, "retryable_error", str(exc), retryable=True)
        except Exception as exc:  # noqa: BLE001
            stop.set()
            logger.exception("handler failed for task %s", task.id)
            self._safe_fail(task, "agent_error", f"{type(exc).__name__}: {exc}")
        finally:
            stop.set()
            beat.join(timeout=5)
        return True

    def _safe_fail(self, task, code, message, retryable=False):
        try:
            self.client.fail(task, code, message, retryable)
        except PlatformError as exc:  # lease already lost -> backend reaper handles it
            logger.warning("could not report failure for %s: %s", task.id, exc)

    def run_forever(self, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        logger.info("worker %s polling for %s", self.worker_id, list(self.handlers))
        while not stop.is_set():
            try:
                worked = self.run_once()
            except Exception:  # noqa: BLE001 - keep the worker alive on transient platform errors
                logger.exception("worker loop error")
                worked = False
            if not worked:
                stop.wait(self.poll_interval)
