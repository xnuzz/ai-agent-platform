"""Agent 1 — SaaS Opportunity Research (agent id SAAS_RESEARCH).

Implements SAAS_OPPORTUNITY_RESEARCH and SAAS_CUSTOMER_RESEARCH per docs/AGENT_1_CONTRACT.md, integrating with the
platform only through `platform_sdk`.
"""
from .config import DEFAULT_LLM_MODEL, Settings
from .handlers import Agent1Handlers, PipelineOptions, Providers

__version__ = "0.1.0"
AGENT_ID = "SAAS_RESEARCH"
TASK_TYPES = ("SAAS_OPPORTUNITY_RESEARCH", "SAAS_CUSTOMER_RESEARCH")

__all__ = ["AGENT_ID", "TASK_TYPES", "DEFAULT_LLM_MODEL", "Settings", "Agent1Handlers", "PipelineOptions",
           "Providers"]
