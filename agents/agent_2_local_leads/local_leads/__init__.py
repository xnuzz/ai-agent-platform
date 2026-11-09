"""Agent 2 - Local Business Lead Finder (agent id LOCAL_LEADS, task type LOCAL_LEAD_DISCOVERY).

Integrates with the platform ONLY via `platform_sdk` (AgentWorker / TaskContext + Result Bundle).
Contract: docs/AGENT_2_CONTRACT.md. Entry point: `python -m local_leads`.
"""
from .config import Settings
from .handler import TASK_TYPE, LocalLeadsAgent

__all__ = ["Settings", "LocalLeadsAgent", "TASK_TYPE", "build_worker"]
__version__ = "0.1.0"


def build_worker(settings: Settings, *, client=None, agent: LocalLeadsAgent | None = None):
    """AgentWorker that serves LOCAL_LEAD_DISCOVERY with the configured providers."""
    from platform_sdk import AgentWorker, PlatformClient

    client = client or PlatformClient(settings.platform_api_url, settings.platform_agent_token)
    agent = agent or LocalLeadsAgent(settings)
    return AgentWorker(client, {TASK_TYPE: agent}, worker_id=settings.worker_id or None,
                       poll_interval=settings.poll_interval, heartbeat_interval=settings.heartbeat_interval)
