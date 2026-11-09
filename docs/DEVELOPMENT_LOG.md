# Development Log

Newest first. Each entry: implemented · files · endpoints · DB · deps · tests · dependencies · breaking · bugs · next.

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
