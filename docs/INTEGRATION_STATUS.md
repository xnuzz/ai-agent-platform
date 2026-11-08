# Integration Status

**Last updated:** 2026-11-08 · Team 3 (Chat 3) · Contract version: API v1 / Result Bundle 1.0
Legend: ✅ Implemented (tested) · 🟡 Partial · 🧪 Mocked · ⬜ Not implemented · ⛔ Blocked

## Main platform (Team 3)
| Area | Status | Notes |
|---|---|---|
| Auth: register, JWT login/refresh, `me` | ✅ | |
| Workspaces, roles (OWNER/ADMIN/DEVELOPER/VIEWER), members API | ✅ | Invitations ⬜ (add existing users only) |
| ResearchTask create/list/detail/cancel/retry | ✅ | Input validated per task type |
| Agent API: claim, lease, heartbeat, results, complete, fail, suppression check | ✅ | |
| Lease expiry reaper (beat + on claim) | ✅ | |
| Result Bundle ingestion (all 7 sections, refs, dedup, idempotency) | ✅ | |
| Approvals: request (agent/user), decide (user), hash pinning, auto customer-research | ✅ | |
| Campaign launch/pause/cancel + compliance gates | ✅ | |
| Email send pipeline (Celery), footer, List-Unsubscribe, daily limit | ✅ | Transport: SMTP Integration or Django backend |
| Suppression list + public unsubscribe (API + page) | ✅ | |
| Integrations (encrypted write-only secrets) | ✅ | Connection "verify" ⬜ |
| Audit log (append-only) | ✅ | |
| Dashboard summary API | ✅ | |
| OpenAPI schema + generated TS types | ✅ | `docs/openapi.yaml`, `frontend/src/api/schema.d.ts` |
| `agents/platform_sdk` (client + worker + keepalive) | ✅ | Used by E2E tests |
| Vue: login/register, dashboard, tasks (both agents), task detail, approval center, ideas, leads+briefs, campaigns+messages, suppression, settings, unsubscribe | ✅ | Browser smoke-tested (Playwright) |
| Vue: edit idea/brief/message, opportunity curation, members, integrations, audit UI | ⬜ | APIs exist |
| Docker compose + Dockerfiles | 🟡 | Written, **not built/run yet** |
| CI workflow | 🟡 | Written, not yet run on GitHub |
| Agent behaviour in tests | 🧪 | Mock handlers with fixed bundles (`tests/support/bundles.py`) |
| Email in dev/test | 🧪 | console / locmem backend — nothing is really sent |
| Follow-up sequences (step>1), reply/bounce webhooks | ⬜ | v2 (ADR-008) |
| GDPR export/erasure, retention job | ⬜ | |
| Per-workspace LLM keys delivered to agents | ⬜ | Agents use env vars for now |
| httpOnly refresh cookie, password reset, email verification | ⬜ | |
| Live updates (SSE/WebSocket) | ⬜ | UI polls every 3–5 s |
| Deployment manifests (`infrastructure/deployment/`) | ⬜ | |

## Agent 1 (Team 1) — `agents/agent_1_saas_research/`
⬜ Not implemented (directory reserved). Backend side is ready and tested with a mock agent.
**What Team 1 needs to do:** implement handlers for `SAAS_OPPORTUNITY_RESEARCH` and `SAAS_CUSTOMER_RESEARCH` per `AGENT_1_CONTRACT.md` using `platform_sdk.AgentWorker`; add a Dockerfile + compose service `agent1` (env `PLATFORM_API_URL`, `PLATFORM_AGENT_TOKEN`, `LLM_*`); add contract tests that validate your bundles against the backend (pattern: `tests/integration/test_end_to_end.py`).

## Agent 2 (Team 2) — `agents/agent_2_local_leads/`
⬜ Not implemented (directory reserved). Backend side ready and tested with a mock agent.
**What Team 2 needs to do:** implement `LOCAL_LEAD_DISCOVERY` per `AGENT_2_CONTRACT.md`; confirm/extend problem codes; Dockerfile + compose service `agent2`; contract tests.

## Requests to Team 3 (agent teams append here)
| Date | From | Request | Status |
|---|---|---|---|
| — | — | — | — |

## Contract changes
| Date | Change | Breaking | Affected |
|---|---|---|---|
| 2026-11-08 | Initial v1 contracts: API, Agent API, Result Bundle 1.0, statuses | — | All |

## Known issues / risks
- A message can remain `SENDING` if the worker dies mid-SMTP call (by design: at-most-once). No UI to resolve yet.
- `LeadSerializer.is_suppressed` costs one query per lead (OK at page_size ≤100).
- Task claiming is FIFO across workspaces; no per-workspace fairness or quotas yet.
- No throttling on agent endpoints (tokens are trusted service credentials).

## Next steps — Team 3 (in order)
1. Push to GitHub, open PR `feature/main-platform` → `main`, confirm CI green.
2. `docker compose up` end-to-end; fix Dockerfiles if needed.
3. Frontend: edit/resubmit flows for ideas, briefs, messages (CHANGES_REQUESTED loop); integrations + members screens.
4. httpOnly-cookie refresh token; password reset.
5. GDPR: data export + erasure endpoint (keep suppression), retention job for stale unconverted leads.
6. Bounce/complaint webhook → automatic suppression; reply tracking → `REPLIED`.
7. Review Team 1/2 PRs against contracts; extend E2E tests with real agent code paths.
