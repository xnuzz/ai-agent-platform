# Development Log

Newest first. Each entry: implemented · files · endpoints · DB · deps · tests · dependencies · breaking · bugs · next.

---

## 2026-11-09 — Team 3 (Chat 3) — Session 2: frontend edit screens + team worktrees

**Implemented**
- Git worktrees for parallel team work: `/home/user/worktrees/agent-1-saas` (`feature/agent-1-saas`), `/home/user/worktrees/agent-2-leads` (`feature/agent-2-leads`); each has an untracked `.env.worktree` pointing at its own test DB (`platform_a1`, `platform_a2`) so suites run concurrently.
- Frontend screens: idea detail/edit/resubmit (`/ideas/:id`), opportunity shortlist/dismiss/reset, lead detail (`/leads/:id`) with contact + legal-basis editing, status moves and embedded project-brief editor (edit/resubmit), campaign offer + per-message editing and resubmission, Settings tabs for members (add/change role/remove) and integrations (create/edit/delete, write-only secret), audit log (`/audit`, ADMIN only).
- Shared components: `LatestDecision` (latest review + reviewer comment), `LinesInput`, `BriefEditor`, `MembersPanel`, `IntegrationsPanel`, `useAction`, `Notice`.

**Bugs found + fixed during browser testing**
- `structuredClone` on Vue reactive proxies crashed the brief editor → JSON-safe `clone()`.
- Success notice rendered inside the block that hides after submit → moved to status row.
- Review panel fired duplicate requests and could show a stale (older) approval → stable watch key + out-of-order response guard.

**API/DB changes:** none. **New dependencies:** none.
**Tests:** `pytest` 51 passed; `npm run build` (vue-tsc + vite) passes; Playwright edit-flow script 16/16 checks, 0 JS errors (script kept outside repo; converting it into a committed e2e suite is a next step).
**Next:** merge Team 1/2 branches; commit a Playwright e2e suite under `frontend/e2e/`.

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
