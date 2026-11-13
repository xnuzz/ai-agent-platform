# AI handoff prompt — paste this into a new AI session

You are joining an existing software project as a senior engineer. Read this whole brief before doing anything,
then confirm your understanding in 5 bullet points and wait for the task.

## What the project is
**Unified AI SaaS Platform** (repo `ai-agent-platform`, GitHub `xnuzz/ai-agent-platform`, branch `main`).
A platform where AI agents find business opportunities and a human approves everything before any outreach.
- **Agent 1 — SaaS research** (`agents/agent_1_saas_research/`, package `saas_research`): finds software-product
  opportunities (pain points, evidence, customer research).
- **Agent 2 — Local lead finder** (`agents/agent_2_local_leads/`, package `local_leads`): finds local small
  businesses that need a website or web work, scans their sites, scores them, writes a project brief and a first
  outreach e-mail. **Most recent work focused here, specifically on the Bulgarian market.**
- **Backend** (`backend/`): Django + DRF + Postgres + Celery/Redis. Owns approvals, compliance, suppression,
  sending. Agents talk to it ONLY through `agents/platform_sdk` (claim task → heartbeat → submit Result Bundle).
- **Frontend** (`frontend/`): Vue 3 + Vite + Tailwind, dark monochrome "deep space glass" design. Key page:
  **Local Business Finder** (`/local-finder`) — live MapLibre map, pins pop in as the agent finds businesses.

## Rules you must follow (from `CLAUDE.md`)
- Read first: `docs/INTEGRATION_STATUS.md`, `docs/DECISIONS.md`, `docs/API_CONTRACTS.md`,
  `docs/AGENT_2_CONTRACT.md`, `docs/WORKFLOWS.md`, `agents/agent_2_local_leads/README.md`.
- Agents never approve or send; the backend enforces approvals and compliance. Status values only from
  `backend/apps/common/enums.py`. No secrets in code.
- Shared interface change ⇒ update docs, regenerate `docs/openapi.yaml` and `frontend/src/api/schema.d.ts`,
  log it in `docs/INTEGRATION_STATUS.md`.
- End of every session: update `docs/INTEGRATION_STATUS.md` and `docs/DEVELOPMENT_LOG.md`
  (implemented / partial / mocked / not implemented / blocked — never claim mocked as done).
- Style: concise communication, production-quality code, smallest correct change.

## How to run it (Windows, PowerShell, repo root)
- Backend stack: `docker compose up -d db redis backend worker beat` (API on http://localhost:8000).
  The backend image bakes the code in: after backend changes run `docker compose up -d --build backend worker beat`.
- Frontend: `cd frontend; npm run dev` → http://localhost:5173 (register an account in the UI).
- `.env` (gitignored) holds generated secrets and the agent tokens `AGENT_1_PLATFORM_TOKEN`, `AGENT_2_PLATFORM_TOKEN`.
- Agent 2 with real data (no API keys needed):
  `$env:PLATFORM_API_URL="http://localhost:8000"; $env:PLATFORM_AGENT_TOKEN=(Select-String '^AGENT_2_PLATFORM_TOKEN=(.+)' .env).Matches.Groups[1].Value; $env:DISCOVERY_PROVIDER="osm"; $env:LLM_PROVIDER="template"; python -m local_leads`
- Tests: `python -m pytest tests/agent_2 --ignore=tests/agent_2/test_agent2_live_contract.py`
  (live-contract and backend tests need Postgres — run them in a container on the compose network).
  `cd frontend; npm run build` must pass.

## Where we are (as of 2026-11-13)
**Committed and pushed to `main`:** merge of the cloud branches (glass redesign, decide reviews from detail
pages, Local Business Finder), page-transition fix, Celery `packaging` dependency fix.

**Done but NOT committed yet (working tree on `main`):**
1. **Real research** — OSM (Overpass) discovery with mirror fallback, categories queried in groups of 4, 2 in
   parallel; missing-website finder (guesses domains, accepts only on name + phone/city match,
   `analyzer/sitefinder.py`); no-contact businesses scored −30 (so they don't flood approvals).
2. **High-potential first + speed** — discovers 2× `max_businesses`, ranks (reachable without own site >
   reachable with site > unreachable; BG mobile = owner-run first), first batch of 3 so pins appear fast,
   crawler concurrency 8. Map auto-zooms to the city (browser geocodes via Nominatim; task gets lat/lon).
3. **Outreach** — language `auto` = local language of the business's country (default in agent, backend input,
   UI); native templates en / bg / de with a sales playbook (personal hook → business impact → one offer with
   local price → one low-friction question; no invented claims); LLM prompts carry the same playbook.
   `market.py`: per-country language, currency, 2026 market hourly rate (BG €25, DE €70, GB £50, US $75 …).
4. **Bulgaria market pack** (`local_leads/bulgaria.py`): chain filter, Bulgarian category words, 18 default BG
   niches, +359 phone normalisation; codes `SOCIAL_MEDIA_ONLY`, `FREE_SUBDOMAIN`, BG-only `PRICES_IN_BGN`
   (euro-only prices since 2026-08-08), `MISSING_COMPANY_INFO` (ЗЕТ чл. 4), `NO_PRIVACY_POLICY`; windows-1251
   handling; ЗЕТ чл. 6 compliance (subject "Търговско предложение:", prices "без ДДС", КЗП register note,
   free-mail addresses → legal basis UNKNOWN); BG sales notes in briefs (recurring revenue, season timing).
   An independent code review's 16 findings were fixed with regression tests.

**Test status:** Agent 2: 72 passed, 1 known flaky timing test on Windows
(`test_agent2_analyzer.py::test_per_host_rate_limit`, fails on unchanged code too). Frontend build passes.
Playwright e2e not run recently.

## Open items / known limits
- **Commit the working tree** (Agent 2 changes belong on `feature/agent-2-leads` per team rules; recent work
  went to `main` directly with the owner's approval — ask which they want).
- **Live Bulgarian discovery run still pending:** public Overpass rate-limited/blocked this machine (429 +
  timeouts). Re-run (e.g. Nessebar or Plovdiv) when it responds, or use Google Places.
- **No API keys yet:** `GOOGLE_PLACES_API_KEY` (much better data: phones + reliable website field) and an
  Anthropic `LLM_API_KEY` (LLM-written briefs/e-mails). Without them OSM + templates are used.
- Requested from Team 3 (backend): enforce the BG subject prefix and import the КЗП opt-out register into
  suppression (logged in `docs/INTEGRATION_STATUS.md`).
- A local test account (`e2e-…@example.test`, workspace "E2E map test") exists in the dev database from browser
  testing; the owner's own workspace is separate.

Start by reading the files listed under "Rules", run the tests, and report anything that contradicts this brief.
