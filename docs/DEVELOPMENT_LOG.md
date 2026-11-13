# Development Log

Newest first. Each entry: implemented · files · endpoints · DB · deps · tests · dependencies · breaking · bugs · next.

---

## 2026-11-13 — Team 3 (Lead Architect) — Stability + security hardening, BG compliance gate

**Implemented (tested)**
- **BG commercial-subject gate in the backend (ADR-018):** outreach to a BG lead needs a subject starting "Търговско предложение"/"Търговско съобщение"; checked at launch (`409 compliance_blocked`, reason `commercial_subject_marker_missing`) and again per message at send. Agent 1 now prefixes BG subjects (`saas_research/pipeline/outreach.py::commercial_subject`); Agent 2 already did. Fixtures/e2e seed updated.
- **Audit fixes** (independent security review, 9 confirmed findings, all fixed with tests in `backend/tests/test_hardening.py`):
  daily send limit race (quota reserved under a workspace row lock; in-flight `SENDING` counts) · message/campaign cancel vs send race (row locks) · deactivated workspaces no longer send, resume or get tasks claimed · webhook `REPLY` must match our Message-ID (address fallback could mark another workspace's lead REPLIED) · provider errors stored/logged as exception type + SMTP code only (no recipient address); GDPR erasure also clears `error` · ADMIN can no longer demote/remove an OWNER · throttle identity ignores client `X-Forwarded-For` (`NUM_PROXIES`, default 0) and throttle counters use a shared Redis cache when not DEBUG (`USE_REDIS_CACHE`, `CACHE_URL`) · request bodies > `MAX_REQUEST_BYTES` (10 MiB) refused with 413 before parsing · SMTP integrations: ports 25/465/587/2525 only, hosts resolving to private/loopback/link-local refused unless `SMTP_ALLOW_PRIVATE_HOSTS` (default = DEBUG).
- `/healthz` now checks the database (503 when unreachable).
- **Windows test failures root-caused (not hidden):** `test_per_host_rate_limit` — the TLS client was built inside the reserved rate-limit slot (~40 ms on Windows), so requests went out late and the next slot early; client now built before the slot, limiter schedules from the slot and uses `perf_counter`. `test_end_to_end` 500 on unsubscribe — `MEDIA_URL` unset made Django's live-server media handler intercept every path (crashes on `:` in signed tokens on Windows); set `MEDIA_URL = "media/"`.

**Files:** `backend/apps/outreach/{services,views,tasks,webhooks}.py`, `backend/apps/{accounts/views,orchestration/services,privacy/services,integrations/serializers}.py`, `backend/apps/common/middleware.py` (new), `backend/config/{settings,settings_test,urls}.py`, `agents/agent_2_local_leads/local_leads/analyzer/fetcher.py`, `agents/agent_1_saas_research/saas_research/pipeline/outreach.py`, tests, `docs/DECISIONS.md` (ADR-018).
**API/contract:** no endpoint or schema change (`docs/openapi.yaml` regenerated: identical). New compliance reason code, new 413 error code `payload_too_large`, new settings env vars (above).
**Tests:** full `pytest` on Windows + local Postgres: **247 passed, 0 failed** (incl. the 2 that failed on Windows before; 7 new in `test_hardening.py`, 2 BG-gate, 1 healthz). `npm run build` passes. Playwright e2e and Docker not run (no Docker daemon).
**Not done / blocked:** КЗП opt-out register import — no public download found (kzp.bg offers only a per-address check form; registration is by legal entities) → needs a product decision. Legal wording of ЗЕТ чл. 6 not re-confirmed (lex.bg fetch failed); counsel review needed. Agent 2 scoring confidence/value model not changed this session.

---

## 2026-11-11 — Team 2 — Agent 2: Bulgaria market pack

**Implemented** (`local_leads/bulgaria.py` + wiring): small-business filter (chains/brands out), Bulgarian category words and 18 default BG niches, owner-run mobile ranking, +359 phone normalisation; new codes `SOCIAL_MEDIA_ONLY`, `FREE_SUBDOMAIN`, BG-only `PRICES_IN_BGN` (euro-only since 2026-08-08), `MISSING_COMPANY_INFO` (ЗЕТ чл. 4), `NO_PRIVACY_POLICY`; windows-1251 detection and `<meta>` charset decoding; Bulgarian booking words; ЗЕТ чл. 6 compliance (subject "Търговско предложение:", "без ДДС", КЗП register note, free-mail → UNKNOWN); BG sales notes in briefs (recurring revenue, season timing, euro update); Facebook pages no longer deduped by domain nor sent as the business website; OSM categories grouped 4 per query.
**Research (sources in the session):** euro adoption timeline (evroto.bg, BTA, Sofia Globe), ЗЕТ current text (ДВ бр. 55/2026) чл. 4 and чл. 6, NSI/Eurostat website adoption (~half of small enterprises).
**Review:** independent code review found 16 issues (4 HIGH: lost/merged Facebook-only leads, false legal findings on windows-1251 sites, missed Bulgarian privacy wording, free-mail treated as legal entity); all HIGH/MEDIUM and most LOW fixed with regression tests.
**Real checks (not mocked):** BG checks run against 5 live Bulgarian sites from earlier runs; findings verified against raw HTML (no false company-info claim on a site that shows "ЕООД"). **Live discovery run in Nessebar failed:** public Overpass rate-limited / unreachable after a day of testing (429 + connection timeouts) - grouping added to reduce query count; re-run when Overpass is reachable or use Google Places.
**Tests:** Agent 2: 72 passed, 1 known Windows timing flake. Backend unchanged (problem codes are free-form).
**Not done:** КЗП register is not machine-checked (no API used); subject prefix enforced agent-side only (backend does not validate) - request to Team 3 below.

---

## 2026-11-11 — Team 2 — Agent 2 outreach: local language, sales playbook, market pricing

**Implemented**
- Outreach language follows the business's country (`language: "auto"`, new default in the agent, the backend `LeadDiscoveryInput` and the Local Business Finder form; explicit codes still win). Native templates for en / bg / de (formal address); LLM writes any language.
- Sales playbook in the LLM system prompts (personal hook from a measured fact → business impact → one clear offer with local price → one low-friction question; no invented claims/urgency). Templates rewritten to the same structure with per-problem impact lines in all three languages; briefs end with call talking points.
- `market.py`: per-country language, currency and 2026 market hourly rate (40 countries; BG EUR 25, DE EUR 70, GB GBP 50, US USD 75 …), quote-like rounding. Replaces the flat EUR 60/h; `BRIEF_HOURLY_RATE` / `BRIEF_CURRENCY` still override.

**Real run (not mocked):** test workspace, Plovdiv, hotels / dentists / lawyers, 15 businesses → 8 leads, 4 qualified, 5 outreach drafts all in Bulgarian, budgets EUR 250-2,000 by scope. Found and fixed: a Latin city name ("Plovdiv") inside Bulgarian text.
**Files:** `local_leads/{market.py (new),briefs,writing,handler,models,config,discovery/google_places}.py`, `local_leads/llm/templates.py`, README; `backend/apps/orchestration/inputs.py` (default `auto` for lead discovery only); `docs/AGENT_2_CONTRACT.md`; `frontend/src/features/localFinder/catalog.ts`, `components/localFinder/ResearchControls.vue`; tests in `tests/agent_2/`. `docs/openapi.yaml` unchanged (task input is a free-form JSON field).
**Tests:** Agent 2: 64 passed, 1 known Windows timing flake. Backend `test_orchestration.py` + `test_ingestion.py` pass (in a container against Postgres). `npm run build` passes. Playwright not run.
**Not done:** LLM path not run for real (no key); market rates are a static, sourced estimate.

---

## 2026-11-11 — Team 2 + Local Business Finder — high-potential first, city auto-zoom, faster first results

**Implemented**
- Agent 2: discovers 2× `max_businesses`, ranks before cutting (reachable without a website > reachable with a website > unreachable); first batch is 3 businesses so leads appear on the map early; OSM category queries run 2 in parallel (public Overpass per-client limit); `CRAWLER_CONCURRENCY` default 4 → 8 (politeness stays per host).
- Local Business Finder: the research drawer geocodes the city with OSM Nominatim (on city/country change and at submit, 5 s timeout, fails silently) → map flies to the city, search circle drawn, task input gets `latitude/longitude` (map frames the city as soon as the run starts; agent skips its own geocoding). A centre picked on the map is never overridden. Empty-state card no longer covers the map while a run is queued/running.

**Real run (browser, not mocked):** test workspace, Plovdiv 3 km, dentist / hair salon / auto repair, 12 businesses: map zoomed to Plovdiv on entering the city; discovery 99 s (Overpass slow), first 3 leads on the map at 137 s with toasts, completed at 175 s, 8 leads.
**Files:** `agents/agent_2_local_leads/local_leads/{handler,config,discovery/osm}.py`, README; `frontend/src/components/localFinder/{ResearchControls,BusinessMap}.vue`; tests `tests/agent_2/{test_agent2_discovery,test_agent2_scoring_briefs}.py`. **API/DB/deps:** none (Nominatim is called from the browser; a CSP must allow `nominatim.openstreetmap.org` in `connect-src`).
**Tests:** `npm run build` passes; Agent 2 unit tests pass (except the known Windows timing flake). Playwright **not run** (would share the running backend/agent).
**Limits:** discovery speed is bound by public Overpass (often 30–60 s per query); Google Places would be much faster.

---

## 2026-11-11 — Team 2 — Agent 2: real OSM research, website lookup, contactability

**Implemented**
- OSM discovery: one Overpass query per category (a busy public instance times out on a big union; one failed category no longer loses the run), results interleaved across categories, comma-separated `OSM_OVERPASS_URL` mirrors tried in order on 429/5xx/timeout, HTTP timeout 90 s.
- `analyzer/sitefinder.py` + `FIND_MISSING_WEBSITES` (default on): businesses without a listed website get a few guessed domains (`<name>.<ccTLD>`, `.com`, hyphenated; Cyrillic transliterated); a site is accepted only if the page shows the name and the phone or city. Found sites are scanned like listed ones; `source_data.website_found` records how.
- Scoring: no e-mail and no phone → −30 (was −10). Unreachable no-website businesses become DISQUALIFIED instead of flooding approvals.

**Real run (not mocked):** Plovdiv, BG, dentists + hair salons, 10 businesses → task COMPLETED, 6 leads stored, 0 qualified (4 with no website and no contact data, 2 sites with minor issues). Probe of 60 OSM businesses: 43 without website tag, 38 without phone or e-mail.
**Files:** `local_leads/{discovery/osm.py,analyzer/sitefinder.py,handler.py,scoring.py,config.py}`, `README.md`, `tests/agent_2/{test_agent2_discovery,test_agent2_sitefinder,test_agent2_scoring_briefs,test_agent2_handler,test_agent2_live_contract}.py`. **API/DB/deps:** none.
**Tests:** `tests/agent_2` (excluding the live-server contract test, which needs Postgres): 61 passed, 1 failed (`test_per_host_rate_limit`, timing flake on Windows, fails on the unchanged code too).
**Not done / blocked:** Google Places not run for real (no key); LLM not run for real (no key; template text used). Domain guessing found no sites in the real sample.
**Next:** run with `DISCOVERY_PROVIDER=google_places` + key; optional web-search lookup for missing websites.

---

## 2026-11-11 — Team 3 — Celery worker/beat crash fix

- `backend/requirements.txt`: added `packaging>=24`. `kombu.transport.redis` imports it without declaring it, so `worker` and `beat` exited on start in a fresh `python:3.13-slim` image (`ModuleNotFoundError: No module named 'packaging'`).
- `layouts/AppLayout.vue`: routed view wrapped in one root element so the page `<Transition>` can animate multi-root views (Vue warning).
- **Tests:** rebuilt with `docker compose up --build`; worker logs `celery@… ready`, beat running. `npm run build` passes. `pytest` not re-run.

---

## 2026-11-11 — Team 3 — merged cloud branches into `main` (local)

- Merged `claude/fervent-tesla-4z396z` (glass redesign) and `claude/new-session-54ipze` (decide reviews from detail pages) on top of `origin/main` (incl. PR #3 Local Business Finder).
- Conflicts resolved: `style.css` keeps the redesign tokens; the locked-field `.input:disabled` style was re-expressed in dark tokens (keeps `cursor: not-allowed`, checked by e2e). `LatestDecision.vue` keeps the in-place decide UI, recoloured to dark tokens (`warn`/`bad`/`line`/`silver`).
- **Tests:** `npm run build` passes. Playwright and `pytest` not re-run in this merge (no backend change).

---

## 2026-11-09 — Frontend redesign session — monochrome "deep space" glass UI

**Implemented (visual/UX only; no API, store or business-logic changes)**
- Design system in `frontend/src/style.css`: CSS-variable tokens (surfaces, glass depths, lines, text, status, viz ramp, shadows, blur, radii, motion) mapped into Tailwind `@theme`; component classes `.card`/`.glass-nav`/`.glass-pop`, `.btn-primary|secondary|danger|ghost` (white primary), `.input`, `.label`, `.table`, `.chip`, `.segmented`, `.kicker`, `.link`, `.skeleton`; global focus ring, dark native dropdowns, page/overlay transitions, global reduced-motion rule. Inter self-hosted.
- `StarField.vue` (canvases painted once + CSS twinkle; drift only on auth pages), `AppIcon.vue` (inline icon set), `BrandMark.vue`, `StatTile.vue`, `charts/DonutChart.vue`, `charts/BarList.vue`, `charts/OpportunityMap.vue`, `charts/palette.ts`.
- Layout: floating glass sidebar with icons, illuminated active item, workspace switcher, collapsible rail (persisted), mobile drawer + top bar; routes fade/scale between pages.
- Pages: dashboard rebuilt (5 KPI tiles, agent activity, research-task donut, pipeline segmented bars, leads by source); tasks (segmented agent picker); approvals (segmented status, type lanes with counts, illuminated selection, sticky detail); software ideas (interactive opportunity map: pain × score, size = evidence, brightness = curation; select → scroll to card); login/reset/unsubscribe (glass, brand); settings (segmented tabs); every other page via the token mapping. Status badges reduced to neutral pills, colour only for ok/warn/error, white pulse for running.
- Local Business Finder: monochrome map style, white/silver markers (green/red only for approved/rejected), glass clusters/popups/tooltips/MapLibre controls, white charts, illuminated selected card, glass drawers and toasts.

**Files:** `frontend/src/style.css`, `App.vue`, `layouts/AppLayout.vue`, `index.html`, `main.ts`, all `views/*`, shared `components/*`, `components/localFinder/**`, `features/localFinder/mapStyle.ts`; new components listed above. **New dependency:** `@fontsource-variable/inter@5.3.0` (OFL, fonts only).
**Tests:** `npm run build` passes; Playwright 14/14 unchanged (selectors kept stable); screenshots at 1440, 1920, tablet, phone (no horizontal overflow, no JS errors); collapsed rail and mobile drawer checked. `pytest` unaffected (no backend change).
**Not verified:** basemap tiles (host blocked here); GPU cost of backdrop blur on low-end devices.
**Next:** check the map with real tiles; consider a "reduce transparency" setting that swaps glass for solid surfaces.

---

## 2026-11-09 — Agent 2 dashboard UI session — Local Business Finder (`/local-finder`)

**Implemented (frontend only, existing endpoints only)**
- Full-screen route `/local-finder` with its own top navigation (logo, Dashboard / Local Business Finder / SaaS Opportunity Research / Approvals, business search, notifications = pending approvals + activity, agent status, profile with workspace switch + sign out); linked from the main sidebar.
- Left: business list — monogram avatar, name, category, location, score ring, top problem, review state; search, sort, 8 filters with counts, research-run selector, arrow-key navigation, "no map pin" for businesses without coordinates.
- Centre: MapLibre GL 6 dark map (custom OpenMapTiles style on OpenFreeMap tiles), clustered HTML markers (new / high-potential glow / reviewed / approved / rejected), hover tooltip, popup with "Open details", selection fly-to + highlight, discovery drop-in + ripple, auto-framing until the user moves the map, search-radius circle, pick-centre-on-map, legend, degraded mode when tiles fail; three SVG charts below (discoveries over time, qualified opportunities by category, score distribution) with tooltips and sr-only tables.
- Right: agent status (IDLE / waiting / SCANNING + LIVE indicator / unresponsive / COMPLETED / FAILED / stopped), country, city/region, radius, current stage + message, progress ring; New research / Stop (two-step) / Retry; six KPIs with rings and 24 h trends; live activity feed + connection state.
- Research configuration drawer → `LOCAL_LEAD_DISCOVERY` input: country (all ISO-3166 via `Intl`), city, region, neighbourhood (sent as note), map-picked centre + radius, categories, development services → `checks`, min score, max businesses, language, notes.
- Detail workspace (drawer, 5 tabs): business info + coordinates; website analysis from `WEBSITE_SCAN` facts (mobile, measured accessibility, broken links, missing functionality, technical issues; opt-in sandboxed preview); opportunity (problems with evidence links, recommended solution, why it benefits, source URLs); project (scope, tech, effort → derived complexity/weeks, budget as hypothesis, Edit project via `BriefEditor`); outreach (channel, recipient, legal basis, message, offer, edit + submit, approve; follow-up shown as not available). Footer: Approve lead / Reject lead / Request more research.
- Live transport: adaptive polling + snapshot diff → documented events (ADR-016); reconnect with backoff; first snapshot is a silent baseline.
- Dev-only demo feed (`?demo=1`, excluded from production bundles, clearly labelled).

**Files:** `frontend/src/views/LocalBusinessFinderView.vue`, `frontend/src/components/localFinder/**` (14 components), `frontend/src/features/localFinder/{model,events,liveFeed,analysis,workspace,catalog,mapStyle}.ts`, `features/localFinder/demo/demoFeed.ts`, `frontend/src/stores/localFinder.ts`, `frontend/src/api/localFinder.ts`; edits: `router/index.ts`, `layouts/AppLayout.vue` (nav link), `style.css` (`.btn-accent`), `env.d.ts`, `vite.config.ts` (MapLibre chunk), `e2e/seed.py` (`empty`, `stream` modes), new `e2e/local-finder.spec.ts`.
**API/DB:** none. **New dependency:** `maplibre-gl@6.16.0` (BSD-3).
**Bugs found in browser testing and fixed:** MapLibre worker URL broken under Vite (fixed with `setWorkerUrl` + `?url` asset); `.maplibregl-map{position:relative}` overrode the container's `absolute inset-0`, collapsing the map to 300 px and clipping markers (inline style); empty-state overlay swallowed the pick-on-map click; Escape only worked with focus inside a drawer (single page-level handler).
**Tests:** `npm run build` passes; Playwright 14/14 (13 existing + `local-finder.spec.ts`: configure → start → mock agent streams 3 batches → toasts, markers, KPIs, unmapped note → filters/search → popup → detail tabs → approve lead + outreach → request more research → archive); manual screenshots at 1440, 1920, tablet (1024) and phone (iPhone 13): no horizontal overflow, no JS errors. `pytest` 223 passed (backend unchanged).
**Mocked:** demo feed (dev only); the e2e agent (`seed.py stream`) is a mock with fixed fictional data. **Not verified:** real basemap tiles (host blocked here), real Agent 2 discovery data.
**Not implemented / blocked:** pause/resume (no platform support — requested), push events (polling), follow-up messages (ADR-008).
**Next:** verify tiles on a networked machine; Team 3 decisions on pause/resume, SSE and lead filters (INTEGRATION_STATUS › Requests).

---

## 2026-11-09 — Team 3 — Session 4: decide reviews from detail pages

**Trigger:** idea detail page for a `WAITING_FOR_APPROVAL` idea was a dead end. It showed "Latest review: PENDING, awaiting decision" but gave no way to decide, and the locked fields looked editable.

**Implemented**
- `LatestDecision`: new `canDecide` / `approveHint` props and a `decided` event. While the latest approval is `PENDING`, reviewers get Approve / Request changes / Reject plus a comment box in place (calls `approvals/{id}/decide/`; the backend still enforces role, state and stale-content checks). The agent's request summary is shown too.
- Wired into idea detail (hint: approving queues Agent 1 customer research), `BriefEditor` (lead page) and campaign detail (hint: approving sends nothing). Each page reloads after a decision, so `CHANGES_REQUESTED` unlocks editing right away.
- `.input` now has disabled styling (muted background, `not-allowed` cursor, no resize handle), which also applies inside a disabled `<fieldset>`. `LinesInput` hides its placeholder when disabled.

**Files:** `frontend/src/components/{LatestDecision,BriefEditor,LinesInput}.vue`, `frontend/src/views/{IdeaDetailView,CampaignDetailView}.vue`, `frontend/src/style.css`, `frontend/e2e/edit-flows.spec.ts`.
**API/DB/deps:** none. No contract change.
**Tests:** `npm run build` passes. Playwright 14/14 locally against Postgres 16 (new test: idea is locked and looks disabled while pending, then Request changes in place unlocks editing).
**Not done:** `pytest` not re-run (no backend change).
**Noted, not changed (Team 1 dir):** with mock providers, Agent 1's fake LLM writes a Python list into idea text (`"(sources ['S16', 'S17'])"`, `saas_research/llm/fake_provider.py`). This only affects 🧪 mock output.

---

## 2026-11-09 — Team 3 (Chat 3) — Session 3: e2e suite, GDPR, email events, auth hardening

**Implemented**
- Playwright browser e2e suite (`frontend/e2e`, 13 tests, mock agents seeded via the real API) + CI `e2e` job.
- GDPR: `privacy/export` + `privacy/erase` (ADMIN, pseudonymous audit), `Workspace.data_retention_days` + daily retention job; Settings › Privacy.
- Inbound email-events webhook (HMAC + timestamp): hard bounce / complaint / unsubscribe → suppression; reply → lead `REPLIED`.
- Auth (ADR-014): httpOnly refresh cookie, rotation + blacklist, logout, password reset (no enumeration) and change; Settings › Account; login page "Forgot password?" + `/reset-password`.

**Bugs found by the browser tests and fixed:** logout fired without awaiting (navigation could cancel the revoke); API client threw on empty 202 bodies; auth/webhook views returned 403 instead of 401 on bad credentials.

**DB:** migrations `accounts.0002_workspace_data_retention_days`, simplejwt `token_blacklist`.
**Breaking:** login body no longer contains `refresh` (frontend updated; agents unaffected).
**New settings:** `EMAIL_WEBHOOK_SECRET`, `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_SECURE`, `AUTH_THROTTLE_RATE`, `PASSWORD_RESET_TIMEOUT_SECONDS`.
**Tests:** `pytest` 223 passed; Playwright 13/13; `npm run build` passes; OpenAPI/TS regenerated.
**Not done / blocked:** Docker never built (no daemon here); ESP adapters for the webhook; email verification + invitations.
**Next:** pick an email provider and write its webhook adapter; email verification + invitations; build Docker on a machine with Docker.

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
