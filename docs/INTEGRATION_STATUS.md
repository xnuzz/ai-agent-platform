# Integration Status

**Last updated:** 2026-11-13 · Team 3 stability/security session · Contract version: API v1 / Result Bundle 1.0 (unchanged)
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
| Campaign launch/pause/cancel + compliance gates | ✅ | 2026-11-13: BG commercial-subject marker gate at launch + send (ADR-018); deactivated workspaces stop sending/claiming |
| Email send pipeline (Celery), footer, List-Unsubscribe, daily limit | ✅ | Transport: SMTP Integration or Django backend. 2026-11-13: daily limit race-free (workspace lock, SENDING counts); cancel vs send locked; provider errors stored without addresses |
| Suppression list + public unsubscribe (API + page) | ✅ | |
| Integrations (encrypted write-only secrets) | ✅ | Connection "verify" ⬜. SMTP host/port validated (no private hosts unless `SMTP_ALLOW_PRIVATE_HOSTS`) |
| Audit log (append-only) | ✅ | |
| Dashboard summary API | ✅ | |
| `/healthz` checks DB (503 on failure); 413 for bodies > `MAX_REQUEST_BYTES`; throttles ignore client X-Forwarded-For (`NUM_PROXIES`), shared Redis cache when not DEBUG | ✅ | 2026-11-13; Redis cache path not exercised here (tests use LocMem) |
| OpenAPI schema + generated TS types | ✅ | `docs/openapi.yaml`, `frontend/src/api/schema.d.ts` |
| `agents/platform_sdk` (client + worker + keepalive) | ✅ | Used by E2E tests |
| Vue: login/register, dashboard, tasks (both agents), task detail, approval center, ideas, leads+briefs, campaigns+messages, suppression, settings, unsubscribe | ✅ | Browser smoke-tested (Playwright) |
| Browser e2e suite (`frontend/e2e`, Playwright, 14 tests, mock agents) | ✅ | Runs in CI `e2e` job |
| Vue: decide a PENDING review in place on idea / project brief / campaign pages (Approve · Request changes · Reject + comment); locked fields visibly disabled | ✅ | Same `approvals/{id}/decide/` endpoint as the Approval center (DEVELOPER+); browser-tested |
| Vue: edit + resubmit idea / project brief / campaign offer / messages (CHANGES_REQUESTED loop, reviewer comment shown) | ✅ | Browser-tested (Playwright, 16 checks) |
| Vue: lead detail (contact, legal basis, status moves), opportunity curation, members, integrations (write-only secret), audit log | ✅ | Browser-tested; audit log ADMIN-only route |
| Vue: member invitations, integration "test connection", audit export | ⬜ | Backend support missing |
| Docker compose + Dockerfiles | ⛔ | Written, never built: no Docker daemon in the dev container. Needs a machine with Docker |
| CI workflow (backend, frontend, browser e2e) | ✅ | Green on GitHub for PR #1; e2e job added 2026-11-09 |
| Agent behaviour in tests | 🧪 | Mock handlers with fixed bundles (`tests/support/bundles.py`) |
| Email in dev/test | 🧪 | console / locmem backend — nothing is really sent |
| Inbound email events webhook: hard bounce / complaint / unsubscribe → suppression, reply → lead REPLIED | ✅ | HMAC + timestamp signed; 7 tests |
| Provider adapters for that webhook (SES, Mailgun, Postmark) | ⬜ | Need a relay or adapter per provider |
| Follow-up sequences (step > 1) | ⬜ | v2 (ADR-008); reply detection now exists via webhook |
| GDPR export + erasure (API + Settings › Privacy), retention job (daily, per-workspace days) | ✅ | 5 unit tests + browser test |
| Per-workspace LLM keys delivered to agents | ⬜ | Agents use env vars for now |
| httpOnly refresh cookie + rotation/blacklist, real logout, password reset + change (ADR-014) | ✅ | 8 backend + 4 browser tests |
| Email verification on signup, member invitations | ⬜ | |
| Live updates (SSE/WebSocket) | ⬜ | UI polls every 3–5 s; the Local Business Finder derives `research.*`/`business.*` events from polled snapshots (ADR-016) |
| **Vue: Local Business Finder (`/local-finder`, Agent 2 dashboard)** — top nav, business list (search, sort, 8 filters, run selector, keyboard nav), MapLibre dark map (clustered HTML markers, 5 marker states, hover tooltip, popup, selection fly-to, discovery ripple, search-radius circle, pick-centre-on-map), live toasts + activity feed, agent status/progress, 6 KPIs, 3 charts, research configuration drawer (city geocoded via Nominatim → map auto-zooms to the city), 5-tab detail workspace | ✅ | Browser-tested against the real API with a MOCK streaming Agent 2 (`e2e/local-finder.spec.ts`); only existing endpoints; responsive (phone/tablet/desktop checked) |
| Finder actions: start / stop / retry run; approve / reject lead (brief approval) or archive lead; request more research (`CHANGES_REQUESTED` + comment); edit project (BriefEditor); edit outreach (message + offer) + submit; approve outreach (campaign approval) | ✅ | All call documented endpoints; disabled with an explanation when the state does not allow them |
| Finder: pause / resume research | ⛔ | No backend/SDK/agent support — buttons shown disabled with a note; requested below |
| Finder: follow-up message | ⬜ | v1 is step 1 only (ADR-008); shown as "not available" |
| Finder basemap tiles (OpenFreeMap) | 🟡 | Style written against the OpenMapTiles schema but **never rendered with real tiles here** (tile host blocked in the dev container); without tiles the map shows a dark background, markers stay correct and a notice is shown. Verify visually on a networked machine |
| **Vue: monochrome "deep space" glass redesign (all pages)** — design tokens + component classes (ADR-017), star-field background, floating glass sidebar (collapsible on desktop, drawer on mobile), page/overlay transitions, redesigned dashboard (5 KPI tiles, agent activity, task donut, pipeline + source charts), segmented controls (agent picker, approval status, settings), approval "control room" (status + type lanes), Agent 1 opportunity map (interactive nodes: pain × score), monochrome Local Business Finder (map style, markers, charts, popups, drawers) | ✅ | Visual/UX only — no API, store or business-logic changes. Playwright 14/14; screenshots checked at 1440, 1920, tablet, phone; reduced-motion respected |
| Finder demo feed (`?demo=1`) | 🧪 | Development builds only (excluded from production bundles); fictional Sofia businesses, "DEMO DATA" banner, actions disabled |
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
**Updated:** 2026-11-11 · Team 2 · branch `feature/agent-2-leads` · package `local_leads` (README in the directory)

| Area | Status | Notes |
|---|---|---|
| `LOCAL_LEAD_DISCOVERY` handler via `platform_sdk.AgentWorker` (all inputs + defaults, 7 recommended stages, batches of `BATCH_SIZE`=10, evidence for every business + problem) | ✅ | Live contract test vs real backend: claim → bundles accepted → brief + campaign PENDING → launch blocked until both approved → sent with backend footer |
| Website analyzer — real HTTP(S): robots.txt (RFC 9309), per-host rate limit, Crawl-delay, timeouts + deadline, size cap, UA with info URL; HTTPS/redirect, TLS validity/expiry, load time, viewport, title/meta, SEO, CMS version, legacy markup, mixed content, contact form, booking, analytics, security headers, accessibility, broken-link sample | ✅ | Tested only against local test servers (HTTP + HTTPS with a test CA), never the internet. TLS check uses a direct socket (bypasses HTTP proxies) |
| Scoring (deterministic, explained in `qualification_notes`), contacts (generic e-mails preferred, personal ones discarded, honest `legal_basis`), suppression check before drafting | ✅ | |
| Project brief (deterministic scope/hours/budget + LLM prose) and outreach draft written in parallel; one campaign per qualified lead with `project_brief_ref`; both `submit_for_approval` | ✅ | Suppressed contact → brief DRAFT, no campaign; no e-mail → brief only |
| LLM layer: interface + JSON validation + Anthropic provider (structured outputs, default `claude-sonnet-5-5`, env `LLM_PROVIDER/LLM_MODEL/LLM_API_KEY`) + template fallback | 🟡 | Request/response handling tested with the real SDK over a mocked transport; **never called the real API** (no key here). Templates are English only |
| Discovery: OpenStreetMap (Nominatim + Overpass, keyless) | ✅ | **Run for real** 2026-11-11 (Plovdiv, BG) end-to-end against the local backend: 60 businesses discovered, sites scanned, bundle accepted. One Overpass query per category + comma-separated mirror fallback (public Overpass returned 502/504/429 often). OSM data is thin: in the sample 43/60 had no website tag and 38/60 no phone or e-mail |
| Discovery: Google Places (New) Text Search | 🟡 | Unit-tested with mocked HTTP only; **not run for real** (no `GOOGLE_PLACES_API_KEY`). Recommended source for "needs a website" leads (phone + website fields far more complete than OSM). `NO_GOOGLE_BUSINESS_PROFILE` not detected |
| Missing-website lookup (`FIND_MISSING_WEBSITES`, `analyzer/sitefinder.py`): guessed domains, accepted only on name + phone/city match | 🟡 | Unit-tested (mocked HTTP); ran on real OSM data — found no matches in that sample (generic names). Domain guessing misses sites on unrelated domains; a web-search provider would find more |
| **Bulgaria market pack** (`bulgaria.py`): small-business filter, BG categories + 18 default niches, owner-run mobile ranking, `SOCIAL_MEDIA_ONLY` / `FREE_SUBDOMAIN` / `PRICES_IN_BGN` / `MISSING_COMPANY_INFO` / `NO_PRIVACY_POLICY`, ЗЕТ чл. 6 compliance (subject marker, без ДДС, КЗП note, free-mail → UNKNOWN), BG sales notes | 🟡 | Checks verified on live BG sites; live discovery run blocked by Overpass rate limit (re-run pending) |
| Outreach in the business's local language (`language: auto` default; native en/bg/de templates), sales-playbook prompts + templates, per-country market pricing (`market.py`) | ✅ | Real run: Bulgarian drafts with EUR market prices. LLM path not run for real (no key). Backend default for `LOCAL_LEAD_DISCOVERY.language` is now `auto` |
| Prospect ranking (2× over-fetch; reachable without website first), first batch of 3, OSM categories 2 in parallel, crawler concurrency 8 | ✅ | Real browser run: first leads on the map ~40 s after discovery finished |
| Scoring: no e-mail **and** no phone → −30 (was −10), so unreachable NO_WEBSITE businesses are DISQUALIFIED (still submitted) | ✅ | |
| `fake` discovery + `fake` LLM providers | 🧪 | Mocks for tests/offline dev only (`discovery/fake.py`, `llm/fake.py`), log a warning when selected |
| CLI `python -m local_leads` (`--once`, `--check-config`) | ✅ | Smoke-run as a real process against `runserver` (fake providers): task COMPLETED, 3 approvals pending |
| Dockerfile (`agents/agent_2_local_leads/Dockerfile`) | 🟡 | Written; **not built** (no Docker daemon in this environment). Wheel build verified |
| Compose service `agent2` | ⛔ | Commented snippet in the agent README; needs Team 3 (see Requests) |
| Follow-ups (step > 1), reply handling, per-workspace LLM keys | ⬜ | Blocked on platform v2 (ADR-008) / Team 3 |

**Tests:** `tests/agent_2/` (62 + live contract test; `test_per_host_rate_limit` Windows flake **fixed 2026-11-13** (root cause in the fetcher, not the test); analyzer, discovery, LLM, scoring/briefs, handler bundle conformance against the backend `ResultBundle` serializer, live-server contract test). Full `pytest`: 111 passed.

## Requests to Team 3 (agent teams append here)
| Date | From | Request | Status |
|---|---|---|---|
| 2026-11-09 | Team 1 | **Compose:** add service `agent1` to `docker-compose.yml` (ready-to-paste commented snippet in `agents/agent_1_saas_research/README.md` §Docker; build context = repo root, `dockerfile: agents/agent_1_saas_research/Dockerfile`) and add `AGENT_1_SEARCH_PROVIDER=brave`, `AGENT_1_SEARCH_API_KEY=` to `.env.example`. | **Done** 2026-11-09 — added under compose profile `agents` (opt-in: `docker compose --profile agents up`) and without `:?` so the base stack starts without agent keys; untested (no Docker daemon) |
| 2026-11-09 | Team 1 | **CI:** `pip install -e agents/platform_sdk -e agents/agent_1_saas_research` in the backend job so `tests/agent_1` (92 tests incl. a live-server contract test) actually run; today `tests/agent_1/conftest.py` skips them with a warning when `pydantic` is missing. | **Done** 2026-11-09 |
| 2026-11-09 | Team 1 | **SDK:** add `platform_sdk.InvalidInputError` mapped by `AgentWorker` to `fail(code="invalid_input", retryable=False)`. `AGENT_1_CONTRACT.md` lists `invalid_input`, but handlers can currently only produce `agent_error`/`retryable_error`/`CANCELLED`. Agent 1 already raises `saas_research.errors.InvalidTaskInput` and will subclass the new exception once it exists. | **Done** 2026-11-09 — `platform_sdk.InvalidInputError` (covered in E2E test). Team 1 follow-up: make `InvalidTaskInput` subclass it |
| 2026-11-09 | Team 2 | Add compose service `agent2` to `docker-compose.yml` (snippet in `agents/agent_2_local_leads/README.md` §Setup; build `agents/agent_2_local_leads/Dockerfile` with repo-root context). Also add `DISCOVERY_PROVIDER`, `GOOGLE_PLACES_API_KEY`, `CRAWLER_INFO_URL` to `.env.example` (agent section). | **Done** 2026-11-09 — profile `agents`, default discovery `osm` (no key), env defaults so the base stack starts; untested (no Docker daemon) |
| 2026-11-09 | Team 2 | CI (`.github/workflows/ci.yml`): also `pip install anthropic>=2.6,<3` (or `pip install -e agents/platform_sdk -e agents/agent_2_local_leads[test]`). Without it the 13 tests in `tests/agent_2/test_agent2_llm.py` are skipped (`importorskip`); all other Agent 2 tests run with backend deps only. `pytest.ini` needs **no** change (`tests/agent_2/conftest.py` adjusts `sys.path`). | **Done** 2026-11-09 — CI installs `-e agents/agent_2_local_leads` (pulls `anthropic`) |
| 2026-11-09 | Team 2 | FYI: the Business dedupe key uses the hostname only (port ignored), so sites differing only by port collapse into one Business. Harmless in production; Agent 2 tests use distinct loopback IPs. No change required. | **Acknowledged** — intended: one business per host; no change |
| 2026-11-11 | Team 2 | **BG compliance in the backend:** (1) validate that outreach to BG leads keeps a subject starting with "Търговско предложение" (ЗЕТ чл. 6, ал. 1) so a reviewer edit cannot drop it; (2) a way to import the КЗП register of opted-out e-mail addresses into workspace suppression. Agent 2 adds the prefix and a note today. | (1) **Done** 2026-11-13 (ADR-018; launch + send gate). (2) ⛔ **Blocked:** no public download of the КЗП register found (kzp.bg has only a per-address check form) — owner decision needed |
| 2026-11-09 | Agent 2 dashboard (UI) | **Pause/resume research:** `POST research-tasks/{id}/pause|resume/` + a `pause_requested` flag in the heartbeat response + SDK/agent support (stop at checkpoint, resume from last batch). The dashboard shows disabled Pause/Resume until this exists. | Open |
| 2026-11-09 | Agent 2 dashboard (UI) | **Push events:** an SSE endpoint (e.g. `GET events/?workspace=…`) emitting `research.started/progress/completed/failed`, `business.discovered/updated/qualified`. Only `features/localFinder/liveFeed.ts` would change. | Open (polling works meanwhile) |
| 2026-11-09 | Agent 2 dashboard (UI) | **Lead filters:** `ordering=updated_at` / `updated_after=` on `leads/` (cheaper incremental polling) and a `business__first_seen_task` filter so businesses re-discovered by a run (existing leads keep their first `research_task`) can be shown in that run's scope. | Open |
| 2026-11-09 | Agent 2 dashboard (UI) → Team 2 | Always send `latitude/longitude` (businesses without them are list-only on the map) and a short `description`; keep `WEBSITE_SCAN` `metadata.facts` key names stable (listed in `AGENT_2_CONTRACT.md` › dashboard). Optional: act on brief `CHANGES_REQUESTED` (re-research) — the "Request more research" button records the comment only. | Open |
| 2026-11-09 | Team 2 | Nice-to-have: expose per-workspace `Integration(kind=LLM/MAPS)` secrets to agents (task `context`) so Agent 2 can use workspace keys instead of deployment env vars. | **Accepted (backlog)** — tracked under "Per-workspace LLM keys delivered to agents" |

## Contract changes
| Date | Change | Breaking | Affected |
|---|---|---|---|
| 2026-11-08 | Initial v1 contracts: API, Agent API, Result Bundle 1.0, statuses | — | All |
| 2026-11-09 | SDK: new `InvalidInputError` → fail code `invalid_input` (additive) | No | Team 1, Team 2 |
| 2026-11-09 | Auth: login no longer returns `refresh` (httpOnly cookie instead); new logout/password endpoints (ADR-014) | **Yes** (frontend only; agents unaffected) | Team 3 |
| 2026-11-09 | New: `privacy/export`, `privacy/erase`, `webhooks/email-events`, `Workspace.data_retention_days` | No | Team 3 |
| 2026-11-09 | Frontend visual redesign (ADR-017): tokens + glass components, new dependency `@fontsource-variable/inter`. No API/schema change | No | Team 3 (frontend conventions) |
| 2026-11-09 | Frontend: new route `/local-finder` (Agent 2 dashboard) using existing endpoints only; documented the scan-fact keys and fields the dashboard reads (`AGENT_2_CONTRACT.md` › dashboard). No API/schema change, OpenAPI unchanged | No | Team 2 (keep fact keys stable), Team 3 |
| 2026-11-13 | Backend: new compliance reason `commercial_subject_marker_missing` (BG, ADR-018); new error `413 payload_too_large`; Agent 1 prefixes BG subjects. No schema change | No (agents already prefix) | Team 1, Team 2, frontend shows reasons verbatim |
| 2026-11-09 | Team 2: new Agent 2 problem codes `WEBSITE_UNREACHABLE`, `NO_HTTPS_REDIRECT`, `SSL_INVALID_CERTIFICATE`, `SSL_EXPIRING_SOON`, `MIXED_CONTENT` (`AGENT_2_CONTRACT.md`). Additive; backend accepts any `UPPER_SNAKE` code, frontend shows codes verbatim | No | Frontend (display only) |

## Known issues / risks
- Local Business Finder: tile rendering unverified (see above); MapLibre adds ~300 kB gzip, loaded only on `/local-finder` (own chunk); its worker is served as `assets/maplibre-gl-worker-*.mjs` — the static server must send a JavaScript MIME type for `.mjs`.
- Redesign: `backdrop-filter` on many glass cards can cost GPU time on low-end devices; the star field is static (no animation loop) to keep re-blurs rare. Basemap tiles are still unverified here (host blocked).
- Local Business Finder loads at most 1,000 Agent 2 leads (10 pages); a notice is shown when truncated.
- A message can remain `SENDING` if the worker dies mid-SMTP call (by design: at-most-once). No UI to resolve yet; it counts against the daily limit.
- ЗЕТ чл. 6 subject wording is a platform convention pending counsel review (ADR-018).
- `LeadSerializer.is_suppressed` costs one query per lead (OK at page_size ≤100).
- Task claiming is FIFO across workspaces; no per-workspace fairness or quotas yet.
- No throttling on agent endpoints (tokens are trusted service credentials).

## Next steps — Team 3 (in order)
2026-11-13: full `pytest` 247 passed / 0 failed on Windows + Postgres; `npm run build` passes; Playwright + Docker not run this session.
0. Owner decisions: КЗП register handling (no public export found); counsel review of the BG subject marker (ADR-018). Commit the working tree on the team branches.
Done 2026-11-09: GitHub + PR #1 merged (green CI) · Team 1/2 merged, requests resolved · browser e2e suite in CI · GDPR export/erasure/retention · email-events webhook · httpOnly-cookie auth + password reset.
1. ⛔ `docker compose up` end-to-end and fix Dockerfiles — needs a machine with Docker (none in the dev container).
2. Choose an email provider (SES / Mailgun / Postmark) → write its adapter for `webhooks/email-events` and its SMTP/API sender.
3. Email verification on signup + member invitations.
4. Review Team 1/2 PRs against contracts; extend e2e with real agent code paths (fake providers).
5. Local Business Finder: check the basemap with real OpenFreeMap tiles; decide on pause/resume + SSE requests above.
