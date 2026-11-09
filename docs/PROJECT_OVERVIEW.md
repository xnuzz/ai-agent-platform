# Project Overview

One commercial SaaS platform where a developer controls two AI agents from one dashboard:

| Component | Owner | Purpose |
|---|---|---|
| **Agent 1 — SaaS Opportunity Research** (`agents/agent_1_saas_research/`) | Team 1 / Chat 1 | Industry research → problems → software ideas → (approval) → customers, offers, outreach drafts |
| **Agent 2 — Local Business Lead Finder** (`agents/agent_2_local_leads/`) | Team 2 / Chat 2 | Location → businesses → website/tech problems → qualified leads → project briefs + outreach drafts |
| **Main Platform** (`backend/`, `frontend/`, `agents/platform_sdk/`, `infrastructure/`, `tests/`, `docs/`) | Team 3 / Chat 3 (Lead Architect) | Django API + DB, auth, approvals, campaigns, outreach execution, Vue dashboard, agent integration, integration tests |

**Hard rule:** agents research and *prepare*. Only the backend persists shared records, and only the backend — after a human approval — sends anything.

## Repository layout
```
backend/            Django + DRF (apps: accounts, orchestration, research, leads, outreach, approvals, integrations, audit, dashboard)
frontend/           Vue 3 + TS + Vite + Tailwind + Pinia + Router
agents/platform_sdk Python SDK agents MUST use to talk to the backend (Team 3)
agents/agent_1_*    Team 1     agents/agent_2_*   Team 2
infrastructure/     Dockerfiles, deployment
tests/              Cross-component integration tests + shared contract fixtures (tests/support/bundles.py)
docs/               Contracts + handoff (this folder). docs/openapi.yaml is generated — never hand-edit.
```

## Read order for a new session
1. `docs/INTEGRATION_STATUS.md` (what exists, what's blocked, next steps)
2. `docs/DECISIONS.md` (why things are the way they are)
3. `docs/API_CONTRACTS.md` + your agent contract (`AGENT_1_CONTRACT.md` / `AGENT_2_CONTRACT.md`)
4. `docs/WORKFLOWS.md` (status machines and approval gates)

## Local quickstart
```bash
cp .env.example .env   # fill DJANGO_SECRET_KEY, FIELD_ENCRYPTION_KEY
docker compose up      # db, redis, backend:8000, worker, beat, frontend:5173
docker compose exec backend python manage.py create_agent_token --agent SAAS_RESEARCH --name agent1-dev
```
Without Docker: Postgres + Redis running, `pip install -r backend/requirements-dev.txt`, set env vars from `.env.example`, `cd backend && python manage.py migrate && python manage.py runserver`; `cd frontend && npm i && npm run dev`.

Tests (repo root, needs `DATABASE_URL` to a Postgres where the user can create DBs): `pytest`.
API docs: `http://localhost:8000/api/docs/` (Swagger) · schema `docs/openapi.yaml`.

## Git workflow
Branches: `feature/agent-1-saas`, `feature/agent-2-leads`, `feature/main-platform` → PR into `main`. CI (`.github/workflows/ci.yml`) runs backend tests, checks OpenAPI/migration drift and builds the frontend.
