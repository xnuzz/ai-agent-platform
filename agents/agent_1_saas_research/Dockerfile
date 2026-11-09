# Agent 1 — SaaS Opportunity Research worker.
# Build from the REPOSITORY ROOT (needs agents/platform_sdk):
#   docker build -f agents/agent_1_saas_research/Dockerfile -t agent1-saas-research .
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY agents/platform_sdk /app/agents/platform_sdk
COPY agents/agent_1_saas_research /app/agents/agent_1_saas_research
RUN pip install /app/agents/platform_sdk /app/agents/agent_1_saas_research \
    && useradd --create-home --shell /usr/sbin/nologin agent
USER agent
# All configuration via environment (see README.md). No secrets baked into the image.
HEALTHCHECK NONE
ENTRYPOINT ["python", "-m", "saas_research"]
