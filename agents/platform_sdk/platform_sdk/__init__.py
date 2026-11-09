"""Platform SDK: the supported way for Agent 1 / Agent 2 to talk to the backend.

Contract: docs/API_CONTRACTS.md §Agent API. Owned by Team 3; changes go through INTEGRATION_STATUS.md.
"""
from .client import PlatformClient, PlatformError, Task
from .worker import AgentWorker, InvalidInputError, RetryableError, TaskCancelled, TaskContext, new_bundle

__all__ = ["PlatformClient", "PlatformError", "Task", "AgentWorker", "TaskContext", "TaskCancelled",
           "RetryableError", "InvalidInputError", "new_bundle"]
