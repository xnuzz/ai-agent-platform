# Development Log

Newest first. Each entry: implemented · files · endpoints · DB · deps · tests · dependencies · breaking · bugs · next.

---

## 2026-11-09 — Team 1 (Chat 1) — Session 1: Agent 1 (SAAS_RESEARCH) implementation

**Implemented**
- Package `saas_research` (`agents/agent_1_saas_research/`): handlers for `SAAS_OPPORTUNITY_RESEARCH` and `SAAS_CUSTOMER_RESEARCH` on `platform_sdk.AgentWorker`; all contract inputs/defaults honoured; recommended stage names; results streamed in batches; ideas/campaign `submit_for_approval` with explanatory `approval_summary`; customer research uses `task.context.software_idea`; `ctx.check_suppression` before drafting; honest `legal_basis`; `sequence_step` 1; sanitised plain-text bodies.
- Pipeline modules: `research` (deterministic query plan, search, LLM problem extraction with citation enforcement), `scoring` (LLM ratings → deterministic weighted score), `ideas` (generation + recommendation), `customers` (LLM search plan, business assessment, website contact discovery, email type + legal basis), `outreach` (offer + drafts), `bundles` (builders, local contract validator, `BatchSubmitter`).
- Provider layer: `LLMProvider` protocol + Anthropic implementation (default model `claude-sonnet-5-5`, `beta.messages.parse` structured output, `fallbacks: "default"` refusal fallback, one retry on invalid output, 429/5xx/529/network → `ProviderTransientError` ⊂ `platform_sdk.RetryableError`); `SearchProvider` (Brave, SerpAPI) + `PageFetcher` (robots.txt, SSRF guard, size cap); 🧪 deterministic `fake` LLM/search/fetcher.
- CLI `python -m saas_research` (`--once`, `--check-config`; refuses mock providers without `AGENT1_ALLOW_MOCK_PROVIDERS=true`), Dockerfile, README (setup, env, architecture, compose snippet).

**Files:** `agents/agent_1_saas_research/{pyproject.toml,Dockerfile,Dockerfile.dockerignore,README.md}`, `agents/agent_1_saas_research/saas_research/**`, `tests/agent_1/**`, `docs/INTEGRATION_STATUS.md` (Agent 1 section + Requests), this entry.
**API endpoints / DB:** none added or changed (agent uses existing Agent API via SDK only).
**Dependencies:** `anthropic>=2.6,<3` (installed 2.6.0 in the shared venv), `pydantic>=2.7,<3`, `httpx>=0.27`, `platform-sdk` — declared in the package `pyproject.toml`.

**Tests:** `pytest` (repo root) → **143 passed** (51 existing + 92 new in `tests/agent_1`). `pytest tests/agent_1` → 92 passed. Includes `test_live_contract.py`: real handlers + 🧪 mock providers against the live backend (task → claim → bundles accepted → idea approval → auto customer research → campaign WAITING_FOR_APPROVAL → launch blocked before approval → after approval only `LEGITIMATE_INTEREST` leads emailed). Every emitted bundle is also validated with the backend's `ResultBundle` serializer. Manual: package installed into a clean venv (`pip install agents/platform_sdk agents/agent_1_saas_research`), `--check-config` exit codes verified; `python -m saas_research --once` run twice against a local `runserver` (mock providers) → both tasks COMPLETED, campaign WAITING_FOR_APPROVAL.
**Not verified:** real Anthropic API, Brave/SerpAPI, internet fetching (no keys/network targets here — mocked HTTP only); Docker image build (no Docker daemon).

**Dependencies on other teams (Team 3):** compose `agent1` service + `.env.example` vars; CI must install the agent package so `tests/agent_1` run; SDK `invalid_input` mapping. See INTEGRATION_STATUS › Requests to Team 3.
**Breaking changes:** none. **Contract changes:** none.
**Outstanding bugs / limitations:** search country/language codes are passed through as ISO-3166/639-1 without per-provider mapping (unverified against live APIs); no CHANGES_REQUESTED re-submission loop; contact discovery fetches ≤6 pages per candidate sequentially (slow for `max_leads` near 200); businesses without a published email are not submitted as leads.
**Next steps (Team 1):** 1) with real keys, run `--once` on a staging workspace and tune prompts/thresholds (`AGENT1_*` env); 2) verify Brave/SerpAPI country/lang parameters live; 3) subclass `InvalidTaskInput` from the SDK's `InvalidInputError` once added; 4) implement the CHANGES_REQUESTED loop (read reviewer comment, re-submit same refs); 5) parallelise website fetching with a per-host rate limit; 6) build/run the Docker image once compose service exists.

## 2026-11-08 — Team 3 (Chat 3) — Session 1: foundation + contracts

**Implemented**
- Monorepo structure; shared contracts (all `docs/*.md`), ADR-001…013.
- Django backend: 9 apps, models for all canonical entities, status machines, services, REST API v1, Agent API, result-bundle ingestion, approval gates with content hashes, email outreach pipeline with compliance blocks, suppression + public unsubscribe, encrypted integrations, append-only audit, dashboard summary, OpenAPI.
- `agents/platform_sdk` (client, worker with keepalive heartbeats, cancellation, retryable errors).
- Vue 3 frontend: auth, dashboard, task launcher for both agents, task detail with live progress, approval center, ideas, leads/briefs, campaigns + launch, suppression, settings, unsubscribe page.
- Docker compose + Dockerfiles (untested), GitHub Actions CI (not yet run).

**Files:** `backend/**`, `frontend/**`, `agents/platform_sdk/**`, `agents/agent_*/README.md` (placeholders only), `tests/**`, `docs/**`, `infrastructure/**`, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, `pytest.ini`, `CLAUDE.md`, `README.md`.

**API endpoints:** all of `docs/API_CONTRACTS.md` (new).
**DB:** initial migrations for accounts, audit, orchestration, research, leads, outreach, approvals, integrations.
**Dependencies:** backend `backend/requirements.txt`; frontend `frontend/package.json` (Vue 3.5, Router 4.6, Pinia 3, Vite 7, Tailwind 4, TS 5.9).

**Tests:** `pytest` → 51 passed (49 backend unit + 2 cross-component E2E over real HTTP with SDK). `npm run build` (vue-tsc + vite) passes. Manual Playwright smoke: register → create task → mock agent → approve → dashboard, no JS errors.

**Dependencies on other teams:** Teams 1/2 implement agents against `AGENT_1_CONTRACT.md` / `AGENT_2_CONTRACT.md` using the SDK.
**Breaking changes:** none (initial).
**Outstanding bugs:** see INTEGRATION_STATUS › Known issues.
**Next steps:** see INTEGRATION_STATUS › Next steps — Team 3.
