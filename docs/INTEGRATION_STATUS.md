# Integration Status

**Last updated:** 2026-11-09 · Team 3 (Chat 3) · Contract version: API v1 / Result Bundle 1.0
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
| Vue: edit + resubmit idea / project brief / campaign offer / messages (CHANGES_REQUESTED loop, reviewer comment shown) | ✅ | Browser-tested (Playwright, 16 checks) |
| Vue: lead detail (contact, legal basis, status moves), opportunity curation, members, integrations (write-only secret), audit log | ✅ | Browser-tested; audit log ADMIN-only route |
| Vue: member invitations, integration "test connection", audit export | ⬜ | Backend support missing |
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
**Last updated:** 2026-11-09 · Team 1 (Chat 1) · branch `feature/agent-1-saas` · package `saas_research` (see its README)

| Area | Status | Notes |
|---|---|---|
| Handlers `SAAS_OPPORTUNITY_RESEARCH` + `SAAS_CUSTOMER_RESEARCH` via `AgentWorker`/`TaskContext` | ✅ | All contract inputs/defaults honoured; recommended stage names; batched submits; `submit_for_approval` + `approval_summary` on ideas and campaign |
| Pipeline steps (research → scoring → ideas → bundles; customers → offer → outreach) | ✅ | Separate modules, unit-tested |
| Evidence grounding (no fabricated URLs/emails; uncited claims dropped) | ✅ | Enforced in code, tested |
| Suppression check before drafting; honest `legal_basis` (generic → LEGITIMATE_INTEREST, else UNKNOWN); `sequence_step` 1; plain-text bodies w/o signature/opt-out | ✅ | Tested incl. live backend launch (only lawful leads emailed) |
| Local bundle validator + backend `ResultBundle` serializer conformance | ✅ | Every emitted bundle checked in tests |
| Live contract test with real handlers (`tests/agent_1/test_live_contract.py`) | ✅ | Uses 🧪 mock providers; real backend over HTTP |
| CLI `python -m saas_research` (`--once`, `--check-config`) | ✅ | Smoke-run against a local `runserver` with mock providers |
| Anthropic LLM provider (default `claude-sonnet-5-5`, structured JSON output, refusal fallback, error mapping) | 🟡 | Unit-tested with mocked HTTP only. **No API key here → never exercised against the real API** |
| Brave / SerpAPI search providers | 🟡 | Unit-tested with mocked HTTP only. **No keys → never exercised for real** |
| HTTP page fetcher (robots.txt, SSRF guard, size cap) | 🟡 | Unit-tested with mocked transport; not run against the internet |
| `fake` LLM / search / fetcher | 🧪 | Deterministic mocks for tests/dev; CLI requires `AGENT1_ALLOW_MOCK_PROVIDERS=true` |
| Dockerfile (`agents/agent_1_saas_research/Dockerfile`) | 🟡 | Install step verified in a clean venv; **image not built** (no Docker daemon in this environment) |
| Compose service `agent1` | ⛔ | `docker-compose.yml` is Team 3's — snippet in Agent 1 README; requested below |
| `invalid_input` fail code | ⛔ | SDK cannot emit it; Agent 1 reports bad context as `agent_error` — requested below |
| Agent 1 tests in CI | ⛔ | CI installs only backend deps; `tests/agent_1` is skipped (with a warning) without `pydantic` — requested below |
| Re-submission after CHANGES_REQUESTED (idea/campaign edit loop) | ⬜ | Not implemented; a retried task re-submits the same refs idempotently |
| Per-workspace LLM/search keys | ⬜ | Env vars only (platform feature ⬜) |

## Agent 2 (Team 2) — `agents/agent_2_local_leads/`
⬜ Not implemented (directory reserved). Backend side ready and tested with a mock agent.
**What Team 2 needs to do:** implement `LOCAL_LEAD_DISCOVERY` per `AGENT_2_CONTRACT.md`; confirm/extend problem codes; Dockerfile + compose service `agent2`; contract tests.

## Requests to Team 3 (agent teams append here)
| Date | From | Request | Status |
|---|---|---|---|
| 2026-11-09 | Team 1 | **Compose:** add service `agent1` to `docker-compose.yml` (ready-to-paste commented snippet in `agents/agent_1_saas_research/README.md` §Docker; build context = repo root, `dockerfile: agents/agent_1_saas_research/Dockerfile`) and add `AGENT_1_SEARCH_PROVIDER=brave`, `AGENT_1_SEARCH_API_KEY=` to `.env.example`. | **Done** 2026-11-09 — added under compose profile `agents` (opt-in: `docker compose --profile agents up`) and without `:?` so the base stack starts without agent keys; untested (no Docker daemon) |
| 2026-11-09 | Team 1 | **CI:** `pip install -e agents/platform_sdk -e agents/agent_1_saas_research` in the backend job so `tests/agent_1` (92 tests incl. a live-server contract test) actually run; today `tests/agent_1/conftest.py` skips them with a warning when `pydantic` is missing. | **Done** 2026-11-09 |
| 2026-11-09 | Team 1 | **SDK:** add `platform_sdk.InvalidInputError` mapped by `AgentWorker` to `fail(code="invalid_input", retryable=False)`. `AGENT_1_CONTRACT.md` lists `invalid_input`, but handlers can currently only produce `agent_error`/`retryable_error`/`CANCELLED`. Agent 1 already raises `saas_research.errors.InvalidTaskInput` and will subclass the new exception once it exists. | **Done** 2026-11-09 — `platform_sdk.InvalidInputError` (covered in E2E test). Team 1 follow-up: make `InvalidTaskInput` subclass it |

## Contract changes
| Date | Change | Breaking | Affected |
|---|---|---|---|
| 2026-11-08 | Initial v1 contracts: API, Agent API, Result Bundle 1.0, statuses | — | All |
| 2026-11-09 | SDK: new `InvalidInputError` → fail code `invalid_input` (additive) | No | Team 1, Team 2 |

## Known issues / risks
- A message can remain `SENDING` if the worker dies mid-SMTP call (by design: at-most-once). No UI to resolve yet.
- `LeadSerializer.is_suppressed` costs one query per lead (OK at page_size ≤100).
- Task claiming is FIFO across workspaces; no per-workspace fairness or quotas yet.
- No throttling on agent endpoints (tokens are trusted service credentials).

## Next steps — Team 3 (in order)
1. Push to GitHub, open PR `feature/main-platform` → `main`, confirm CI green.
2. `docker compose up` end-to-end; fix Dockerfiles if needed.
3. Merge Team 1 / Team 2 branches (worktrees `/home/user/worktrees/agent-*`), resolve their "Requests to Team 3", run combined tests.
4. httpOnly-cookie refresh token; password reset.
5. GDPR: data export + erasure endpoint (keep suppression), retention job for stale unconverted leads.
6. Bounce/complaint webhook → automatic suppression; reply tracking → `REPLIED`.
7. Review Team 1/2 PRs against contracts; extend E2E tests with real agent code paths.
