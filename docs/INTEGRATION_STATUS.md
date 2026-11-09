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
**Updated:** 2026-11-09 · Team 2 (Chat 2) · branch `feature/agent-2-leads` · package `local_leads` (README in the directory)

| Area | Status | Notes |
|---|---|---|
| `LOCAL_LEAD_DISCOVERY` handler via `platform_sdk.AgentWorker` (all inputs + defaults, 7 recommended stages, batches of `BATCH_SIZE`=10, evidence for every business + problem) | ✅ | Live contract test vs real backend: claim → bundles accepted → brief + campaign PENDING → launch blocked until both approved → sent with backend footer |
| Website analyzer — real HTTP(S): robots.txt (RFC 9309), per-host rate limit, Crawl-delay, timeouts + deadline, size cap, UA with info URL; HTTPS/redirect, TLS validity/expiry, load time, viewport, title/meta, SEO, CMS version, legacy markup, mixed content, contact form, booking, analytics, security headers, accessibility, broken-link sample | ✅ | Tested only against local test servers (HTTP + HTTPS with a test CA), never the internet. TLS check uses a direct socket (bypasses HTTP proxies) |
| Scoring (deterministic, explained in `qualification_notes`), contacts (generic e-mails preferred, personal ones discarded, honest `legal_basis`), suppression check before drafting | ✅ | |
| Project brief (deterministic scope/hours/budget + LLM prose) and outreach draft written in parallel; one campaign per qualified lead with `project_brief_ref`; both `submit_for_approval` | ✅ | Suppressed contact → brief DRAFT, no campaign; no e-mail → brief only |
| LLM layer: interface + JSON validation + Anthropic provider (structured outputs, default `claude-sonnet-5-5`, env `LLM_PROVIDER/LLM_MODEL/LLM_API_KEY`) + template fallback | 🟡 | Request/response handling tested with the real SDK over a mocked transport; **never called the real API** (no key here). Templates are English only |
| Discovery: Google Places (New) Text Search, OpenStreetMap (Nominatim + Overpass, keyless) | 🟡 | Implemented against documented APIs, unit-tested with mocked HTTP only; **not run against the real services** (no keys / network). `NO_GOOGLE_BUSINESS_PROFILE` not detected |
| `fake` discovery + `fake` LLM providers | 🧪 | Mocks for tests/offline dev only (`discovery/fake.py`, `llm/fake.py`), log a warning when selected |
| CLI `python -m local_leads` (`--once`, `--check-config`) | ✅ | Smoke-run as a real process against `runserver` (fake providers): task COMPLETED, 3 approvals pending |
| Dockerfile (`agents/agent_2_local_leads/Dockerfile`) | 🟡 | Written; **not built** (no Docker daemon in this environment). Wheel build verified |
| Compose service `agent2` | ⛔ | Commented snippet in the agent README; needs Team 3 (see Requests) |
| Follow-ups (step > 1), reply handling, per-workspace LLM keys | ⬜ | Blocked on platform v2 (ADR-008) / Team 3 |

**Tests:** `tests/agent_2/` (60 tests: analyzer, discovery, LLM, scoring/briefs, handler bundle conformance against the backend `ResultBundle` serializer, live-server contract test). Full `pytest`: 111 passed.

## Requests to Team 3 (agent teams append here)
| Date | From | Request | Status |
|---|---|---|---|
| 2026-11-09 | Team 2 | Add compose service `agent2` to `docker-compose.yml` (snippet in `agents/agent_2_local_leads/README.md` §Setup; build `agents/agent_2_local_leads/Dockerfile` with repo-root context). Also add `DISCOVERY_PROVIDER`, `GOOGLE_PLACES_API_KEY`, `CRAWLER_INFO_URL` to `.env.example` (agent section). | Open |
| 2026-11-09 | Team 2 | CI (`.github/workflows/ci.yml`): also `pip install anthropic>=2.6,<3` (or `pip install -e agents/platform_sdk -e agents/agent_2_local_leads[test]`). Without it the 13 tests in `tests/agent_2/test_agent2_llm.py` are skipped (`importorskip`); all other Agent 2 tests run with backend deps only. `pytest.ini` needs **no** change (`tests/agent_2/conftest.py` adjusts `sys.path`). | Open |
| 2026-11-09 | Team 2 | FYI: the Business dedupe key uses the hostname only (port ignored), so sites differing only by port collapse into one Business. Harmless in production; Agent 2 tests use distinct loopback IPs. No change required. | FYI |
| 2026-11-09 | Team 2 | Nice-to-have: expose per-workspace `Integration(kind=LLM/MAPS)` secrets to agents (task `context`) so Agent 2 can use workspace keys instead of deployment env vars. | Open |

## Contract changes
| Date | Change | Breaking | Affected |
|---|---|---|---|
| 2026-11-08 | Initial v1 contracts: API, Agent API, Result Bundle 1.0, statuses | — | All |
| 2026-11-09 | Team 2: new Agent 2 problem codes `WEBSITE_UNREACHABLE`, `NO_HTTPS_REDIRECT`, `SSL_INVALID_CERTIFICATE`, `SSL_EXPIRING_SOON`, `MIXED_CONTENT` (`AGENT_2_CONTRACT.md`). Additive; backend accepts any `UPPER_SNAKE` code, frontend shows codes verbatim | No | Frontend (display only) |

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
