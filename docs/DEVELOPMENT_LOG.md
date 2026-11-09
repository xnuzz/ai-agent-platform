# Development Log

Newest first. Each entry: implemented · files · endpoints · DB · deps · tests · dependencies · breaking · bugs · next.

---

## 2026-11-09 — Team 2 (Chat 2) — Session 1: Agent 2 Local Business Lead Finder

**Implemented**
- Package `local_leads` (`agents/agent_2_local_leads/`): `LOCAL_LEAD_DISCOVERY` handler on `platform_sdk.AgentWorker`; all inputs/defaults honoured (location + radius, categories, max_businesses, checks, min_score, language, notes); 7 recommended stages; batched bundles (`BATCH_SIZE` 10) with evidence for every business and problem; deterministic refs (idempotent retries).
- Website analyzer doing real HTTP(S) checks: robots.txt (RFC 9309) + Crawl-delay, per-host rate limit, timeouts + deadline, bounded page size, identifying User-Agent with info URL; HTTPS/redirect, TLS validity/expiry, load time, viewport, meta, SEO, CMS version, legacy markup, mixed content, contact form, booking, analytics, security headers, accessibility, broken-link sample → problem codes.
- Deterministic explained scoring; contact selection (generic preferred, personal discarded, honest legal basis); suppression check before drafting; deterministic estimate (scope/hours/budget); brief + outreach prose written in parallel through an LLM provider layer (Anthropic default via structured outputs, validation, template fallback); one campaign per qualified lead with `project_brief_ref`, both submitted for approval.
- Discovery providers: Google Places (New) Text Search, OpenStreetMap (Nominatim + Overpass); 🧪 fake discovery + 🧪 fake LLM for tests/offline.
- CLI `python -m local_leads` (`--once`, `--check-config`), Dockerfile, README (setup, env, architecture, crawler ethics, compose snippet).
- Contract: 5 additive problem codes (`AGENT_2_CONTRACT.md`).

**Files:** `agents/agent_2_local_leads/**` (new: `pyproject.toml`, `Dockerfile`, `README.md`, `local_leads/**`), `tests/agent_2/**` (new), `docs/AGENT_2_CONTRACT.md` (problem codes), `docs/INTEGRATION_STATUS.md` (Agent 2 section, Requests, Contract changes), this log.
**API endpoints / DB:** none changed (agent uses the existing Agent API through the SDK only).
**Dependencies:** `local-leads` → `platform-sdk`, `httpx>=0.27`, `anthropic>=2.6,<3`; test extra `cryptography` (test CA). Installed `anthropic` 2.6.0 into the shared venv.

**Tests:** `pytest` (repo root, `source .env.worktree`) → **111 passed** (51 existing + 60 new in `tests/agent_2/`: analyzer vs local HTTP/HTTPS servers incl. expired/untrusted/expiring certificates, discovery with mocked HTTP, Anthropic provider with the real SDK over a mocked transport, scoring/contacts/estimates, handler bundles validated with the backend `ResultBundle` serializer, live-server contract test running the real handler end-to-end). `tests/agent_2` re-run 4× without flakes. With `anthropic` unavailable (CI today) 47 pass and `test_agent2_llm.py` is skipped. Manual: `python -m local_leads --once` as a real process vs `runserver` on the isolated DB (fake providers) → task COMPLETED, 3 approvals pending. Wheel build OK. **Not run:** Docker build (no daemon), real Anthropic / Google Places / OSM calls (no keys/network).

**Dependencies on other teams:** Team 3 — compose service `agent2` + `.env.example` vars; CI install of `anthropic` (see INTEGRATION_STATUS › Requests). No backend/SDK changes needed.
**Breaking changes:** none (problem codes are additive).
**Outstanding bugs / limits:** templates English-only (non-`en` tasks fall back to English when the LLM is unavailable; flagged in approval summaries); TLS check opens a direct socket (bypasses HTTP proxies → "unknown" behind strict egress proxies); `NO_GOOGLE_BUSINESS_PROFILE` not detected; booking/analytics detection is keyword-based (homepage + one contact page); load time measures the HTML document only (no rendering/LCP).
**Next steps (Team 2):** 1) run against real providers with keys (Google Places, Anthropic) on a staging backend and tune thresholds/weights on real sites; 2) build + run the Docker image once Team 3 adds the compose service; 3) localised templates (at least `de`, `bg`); 4) optional headless-browser performance check (LCP) behind a flag; 5) Google Business Profile signal from Places data; 6) respond to Team 3 review of the contract additions.

---

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
