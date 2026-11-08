# Unified AI SaaS Platform — rules for every Claude session

Three teams, one product. The repo is the only communication channel.
- Team 1 → `agents/agent_1_saas_research/` · Team 2 → `agents/agent_2_local_leads/` · Team 3 (Lead Architect) → everything else.
- Branches: `feature/agent-1-saas`, `feature/agent-2-leads`, `feature/main-platform` → PR into `main`.

Before coding: read `docs/INTEGRATION_STATUS.md`, `docs/DECISIONS.md`, `docs/API_CONTRACTS.md`, your agent contract, `docs/WORKFLOWS.md`.

Hard rules
- Agents talk to the backend ONLY via `agents/platform_sdk` and the Result Bundle (no DB access, no new endpoints assumed).
- Agents never approve or send. Backend enforces approvals and compliance.
- Status values come only from `backend/apps/common/enums.py`.
- Shared interface change ⇒ update docs + regenerate `docs/openapi.yaml` (`cd backend && python manage.py spectacular --file ../docs/openapi.yaml`) and `frontend/src/api/schema.d.ts` (`cd frontend && npm run gen:api`) + log in `docs/INTEGRATION_STATUS.md`.
- No secrets in code. Don't edit another team's directory; request via INTEGRATION_STATUS "Requests to Team 3".

End of every session: update `docs/INTEGRATION_STATUS.md` and `docs/DEVELOPMENT_LOG.md` (implemented / partial / mocked / not implemented / blocked — never claim mocked as done).

Commands: `pytest` (repo root; needs `DATABASE_URL` Postgres) · `cd frontend && npm run build`.
Communication style: concise. Code quality: production.
