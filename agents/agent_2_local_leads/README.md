# Agent 2 — Local Business Lead Finder (`local_leads`)

**Owner: Team 2.** Agent id `LOCAL_LEADS` · task type `LOCAL_LEAD_DISCOVERY` · contract
[`docs/AGENT_2_CONTRACT.md`](../../docs/AGENT_2_CONTRACT.md). Talks to the platform **only** through
[`agents/platform_sdk`](../platform_sdk) (`AgentWorker` / `TaskContext` + Result Bundle v1.0). The agent never
approves and never sends: it submits leads, project briefs and outreach drafts with `submit_for_approval: true`;
the backend enforces approvals, suppression and compliance.

## What it does
```
input.location ──▶ discovery provider ──▶ businesses (≤ max_businesses, deduped by id + website domain)
   └─ per batch of BATCH_SIZE (default 10):
        SCANNING_WEBSITES   real HTTP(S) checks (robots.txt, rate limit, timeouts, bounded size)
        QUALIFYING          problems → deterministic score → QUALIFIED iff score ≥ min_score (DISQUALIFIED still submitted)
                            ctx.check_suppression(contacts) before any drafting
        WRITING_BRIEFS      ┐ in parallel per qualified lead: estimate (code) + brief text (LLM)
        DRAFTING_OUTREACH   ┘                                  + first e-mail (LLM), template fallback
        SUBMITTING          one Result Bundle: evidence, businesses, leads, project_briefs, campaigns
```
Progress stages: `PLANNING`, `DISCOVERING_BUSINESSES`, `SCANNING_WEBSITES`, `QUALIFYING`, `WRITING_BRIEFS`,
`DRAFTING_OUTREACH`, `SUBMITTING`. Every business cites its listing evidence; every problem cites the
`WEBSITE_SCAN` evidence of the site plus a per-problem evidence item with the measured facts.

Per qualified lead: one **project brief** (summary, problems, proposed solution, scope items, tech stack,
effort hours, budget range + currency) and — if a usable, non-suppressed business e-mail exists — one
**campaign** (`project_brief_ref`, one plain-text message, `sequence_step: 1`). Both `submit_for_approval: true`;
launch is possible only after both are approved (backend gate). Suppressed contact → brief stays DRAFT, no campaign.
No e-mail → brief submitted, no campaign.

## Layout
```
local_leads/
  __main__.py        CLI: python -m local_leads [--once] [--check-config]
  config.py          Settings from env
  handler.py         LocalLeadsAgent (the LOCAL_LEAD_DISCOVERY handler)
  discovery/         provider interface · google_places.py · osm.py · fake.py (🧪 mock)
  analyzer/          fetcher.py (polite HTTP) · tls.py · htmlparse.py · website.py (checks → problem codes)
  problems.py        problem-code catalog: severity, score weight, remediation scope + hours
  scoring.py         deterministic, explained lead score
  contacts.py        e-mail classification, legal basis
  briefs.py          deterministic estimate (approach, scope, hours, budget)
  llm/               provider interface + JSON validation · anthropic_provider.py · fake.py (🧪 mock) · templates.py
  writing.py         brief/outreach prose: LLM structured JSON → validation → template fallback
  bundle.py          Result Bundle builder (sanitised to backend field rules, deterministic refs)
```
Tests live in `tests/agent_2/` (collected by plain `pytest` from the repo root; `conftest.py` adds this
directory to `sys.path`, so the shared `pytest.ini` is unchanged).

## Setup & run
```bash
pip install -e agents/platform_sdk -e "agents/agent_2_local_leads[test]"
export PLATFORM_API_URL=http://localhost:8000
export PLATFORM_AGENT_TOKEN=...      # cd backend && python manage.py create_agent_token --agent LOCAL_LEADS --name agent2
export CRAWLER_INFO_URL=https://your-company.example/bot   # public page describing the crawler
export DISCOVERY_PROVIDER=osm        # or google_places + GOOGLE_PLACES_API_KEY
export LLM_API_KEY=...               # Anthropic key (or ANTHROPIC_API_KEY); LLM_PROVIDER=template for no LLM
python -m local_leads --check-config # validate, print providers + User-Agent
python -m local_leads                # poll forever (SIGTERM/SIGINT to stop); --once = one task then exit
```
Offline dev without any keys: `DISCOVERY_PROVIDER=fake LLM_PROVIDER=fake` (optionally
`FAKE_DISCOVERY_FILE=businesses.json`, a list of objects with `DiscoveredBusiness` fields).

Docker (build from the repo root): `docker build -f agents/agent_2_local_leads/Dockerfile -t local-leads .`

Compose service — **not** added to Team 3's `docker-compose.yml` (requested in INTEGRATION_STATUS); snippet:
```yaml
  # agent2:
  #   build: {context: ., dockerfile: agents/agent_2_local_leads/Dockerfile}
  #   environment:
  #     PLATFORM_API_URL: http://backend:8000
  #     PLATFORM_AGENT_TOKEN: ${AGENT_2_PLATFORM_TOKEN:?create with manage.py create_agent_token}
  #     DISCOVERY_PROVIDER: ${DISCOVERY_PROVIDER:-osm}
  #     GOOGLE_PLACES_API_KEY: ${GOOGLE_PLACES_API_KEY:-}
  #     LLM_PROVIDER: ${LLM_PROVIDER:-anthropic}
  #     LLM_MODEL: ${LLM_MODEL:-}
  #     LLM_API_KEY: ${LLM_API_KEY:-}
  #     CRAWLER_INFO_URL: ${CRAWLER_INFO_URL:?public page describing the crawler}
  #   depends_on: [backend]
  #   restart: unless-stopped
```

## Environment
| Variable | Default | Meaning |
|---|---|---|
| `PLATFORM_API_URL`, `PLATFORM_AGENT_TOKEN` | — (required) | backend URL and `LOCAL_LEADS` agent token |
| `WORKER_ID`, `POLL_INTERVAL`, `HEARTBEAT_INTERVAL` | host-based, `5`, `60` | worker identity / polling / lease keepalive (s) |
| `DISCOVERY_PROVIDER` | `google_places` | `google_places` · `osm` · `fake` (🧪 mock) |
| `GOOGLE_PLACES_API_KEY` | — | required for `google_places` |
| `OSM_OVERPASS_URL`, `OSM_NOMINATIM_URL` | public instances | for `osm` |
| `FAKE_DISCOVERY_FILE` | — | JSON fixture for `fake` |
| `LLM_PROVIDER` | `anthropic` | `anthropic` · `fake` (🧪 mock) · `template` (no LLM) |
| `LLM_MODEL` | `claude-sonnet-5-5` | any model id the provider accepts |
| `LLM_API_KEY` | — | Anthropic API key (if empty the SDK falls back to `ANTHROPIC_API_KEY`) |
| `LLM_EFFORT` | `medium` | `low`…`max`; `none` omits the parameter (models without effort support) |
| `LLM_SERVER_FALLBACK` | `true` | Anthropic server-side refusal fallback (`fallbacks: "default"`, Claude API only) |
| `LLM_TIMEOUT`, `LLM_MAX_RETRIES` | `120`, `2` | SDK timeout (s) / retries (429, 5xx, network) |
| `BATCH_SIZE` | `10` | businesses per submitted bundle |
| `BRIEF_HOURLY_RATE`, `BRIEF_CURRENCY` | `60`, `EUR` | budget = hours × rate (rounded to 50) |
| `CRAWLER_INFO_URL` | placeholder (warns) | contact/info URL in the User-Agent |
| `CRAWLER_MIN_HOST_INTERVAL` | `1.0` | seconds between requests to one host |
| `CRAWLER_MAX_CRAWL_DELAY` | `10` | robots `Crawl-delay` honoured up to this; above → homepage only |
| `CRAWLER_CONNECT_TIMEOUT`, `CRAWLER_READ_TIMEOUT` | `5`, `10` | per request; plus a wall-clock deadline |
| `CRAWLER_MAX_PAGE_BYTES` | `1500000` | bounded download per page |
| `CRAWLER_MAX_LINK_CHECKS` | `8` | broken-link sample (same-site links only) |
| `CRAWLER_CONCURRENCY` | `4` | sites scanned in parallel (different hosts) |
| `CRAWLER_SLOW_PAGE_SECONDS`, `CRAWLER_SSL_EXPIRY_WARNING_DAYS` | `3.0`, `14` | thresholds |
| `CRAWLER_CA_BUNDLE`, `CRAWLER_TRUST_ENV` | system CAs, `true` | TLS trust store / honour proxy env vars |

## Website checks → problem codes
| Check (real HTTP, `analyzer/`) | Code(s) |
|---|---|
| homepage unreachable / DNS / 404 / 5xx | `WEBSITE_UNREACHABLE` |
| final page on `http://`; HTTPS probe fails / works without redirect | `NO_HTTPS` / `NO_HTTPS_REDIRECT` |
| TLS handshake with verification: expired / untrusted / expires < 14 d | `SSL_EXPIRED` / `SSL_INVALID_CERTIFICATE` / `SSL_EXPIRING_SOON` |
| HTML download time > threshold (HIGH if > 2×) | `SLOW_PAGE_LOAD` |
| no `viewport width=device-width` | `NOT_MOBILE_FRIENDLY` |
| missing `<title>` / meta description | `MISSING_META` |
| noindex, no `<h1>`, title length, no canonical | `POOR_SEO` |
| `<meta generator>` CMS below vendor-supported version (WordPress < 6.0, Joomla < 4, Drupal < 10, TYPO3 < 12, PrestaShop < 8) | `OUTDATED_CMS` |
| legacy markup (`<font>`, `<center>`, `<marquee>`, frames, Flash, nested tables) | `OUTDATED_DESIGN` |
| HTTPS page loading `http://` resources | `MIXED_CONTENT` |
| no message form on homepage or contact page | `NO_CONTACT_FORM` |
| booking-type category without booking link/widget | `NO_ONLINE_BOOKING` |
| no analytics script detected | `NO_ANALYTICS` |
| ≥ 3 of CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, HSTS missing | `SECURITY_HEADERS_MISSING` |
| missing alt texts, no `lang`, unlabelled fields, zoom disabled | `ACCESSIBILITY_ISSUES` |
| sampled same-site links returning ≥ 400 / failing | `BROKEN_LINKS` |
| no website in listing | `NO_WEBSITE` |
`NO_GOOGLE_BUSINESS_PROFILE` is in the catalog but **not detected** (no provider signal yet).
`checks` input limits both the reported codes and the requests made (e.g. no link sampling unless `BROKEN_LINKS`).

## Scoring (deterministic)
`score = min(85, Σ weight of distinct problem codes) + contact adjustment` (generic e-mail +10, other
e-mail +3, none −10), clamped 0–100; weights in `problems.py`. `QUALIFIED` iff `score ≥ min_score`.
The full breakdown is written to `qualification_notes`. Budget/hours come from `briefs.py` rules, never
from the LLM; the LLM only phrases them.

## LLM layer
`LLMProvider.generate_json(task, system, prompt, schema)` → dict. Anthropic implementation uses the
Messages API with structured outputs (`output_config.format: json_schema`), `effort`, server-side
refusal fallback, typed error mapping (429/5xx/network → `LLMUnavailable`, refusal → `LLMRefusal`).
Output is re-validated locally (schema + content rules: no sign-off/opt-out text, no placeholders, no
shaming words); on any failure the deterministic template is used and the reviewer sees
"Text by template (reason)" in the approval summary. Templates are English only; when the task language
differs this is stated and the message `language` is set to `en`.

## Contacts & legal basis
Only generic business addresses (info@, office@, name-of-business@ …) are preferred; addresses that look
personal (`firstname.lastname@`) are **discarded** (data minimisation). Generic → `LEGITIMATE_INTEREST` with
a note explaining the assessment (not legal advice); ambiguous → `UNKNOWN` (backend blocks sending until a
human sets it). Suppression is checked with `ctx.check_suppression` before drafting.

## Crawler ethics
- robots.txt fetched once per origin and obeyed (`LocalLeadsBot` token or `*`); RFC 9309 semantics: 4xx → allowed,
  5xx/unreachable → fully disallowed. `Crawl-delay` honoured (capped; capped sites get homepage-only scans).
- ≤ 1 request per host per `CRAWLER_MIN_HOST_INTERVAL` (default 1 s); small, bounded page budget per site
  (robots.txt, homepage, one contact page, HTTPS/HTTP probe, ≤ 8 HEAD link checks; no external links).
- Timeouts + wall-clock deadline + max page size on every request; only `http(s)` URLs.
- User-Agent `LocalLeadsBot/0.1 (+CRAWLER_INFO_URL)` — a URL, never a personal e-mail.
- Only data needed for qualification is collected; no social profiles; listing data keeps provider attribution
  (OSM: "© OpenStreetMap contributors (ODbL)"). Google Places terms restrict caching Places content other than
  place IDs — operators must review provider ToS for their deployment.
- Outreach copy states facts measured on the public site, never shames, and contains no signature/opt-out
  (the backend appends sender identity and the unsubscribe footer).

## Status
See `docs/INTEGRATION_STATUS.md › Agent 2`. 🧪 `discovery/fake.py` and `llm/fake.py` are mocks for tests and
offline development only.
