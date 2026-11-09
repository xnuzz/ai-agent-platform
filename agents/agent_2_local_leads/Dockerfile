# Agent 2 - Local Business Lead Finder worker.
# Build from the REPOSITORY ROOT (needs agents/platform_sdk):
#   docker build -f agents/agent_2_local_leads/Dockerfile -t local-leads .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY agents/platform_sdk /app/platform_sdk
COPY agents/agent_2_local_leads /app/agent_2_local_leads
RUN pip install /app/platform_sdk /app/agent_2_local_leads \
    && useradd --system --uid 10002 --home /app agent \
    && chown -R agent /app
USER agent

# Required at runtime: PLATFORM_API_URL, PLATFORM_AGENT_TOKEN, CRAWLER_INFO_URL and provider settings
# (DISCOVERY_PROVIDER + GOOGLE_PLACES_API_KEY, LLM_PROVIDER/LLM_MODEL/LLM_API_KEY). See README.
CMD ["python", "-m", "local_leads"]
