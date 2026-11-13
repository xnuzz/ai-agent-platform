# Architecture Decision Records

Format: ID · status · decision · why · consequences. Superseding a decision = new ADR referencing the old one.

### ADR-001 · Accepted · Monorepo, single backend, single database
Everything in one repo; Django owns all shared models in one PostgreSQL DB. Agents own no tables.
Why: prompt mandates one platform; avoids competing models. Consequence: schema changes go through Team 3.

### ADR-002 · Accepted · Workspaces are the tenant boundary; scope via `X-Workspace-ID` header
Every business row has `workspace_id`; users act in a workspace selected by header (not URL nesting).
Why: simpler client code, one place to enforce membership (`WorkspaceScopedMixin`). Consequence: foreign/missing workspace → `400 workspace_required`; other workspaces' objects → 404.

### ADR-003 · Accepted · Agents pull work over HTTP with leases (not Celery, not DB access)
Agents call `claim → heartbeat → results → complete|fail` with an agent token and per-claim `lease_id`.
Why: agents stay independent Python processes (any host, any deps), no shared broker contract, crash-safe via lease expiry, easy to test. Alternatives rejected: Celery cross-service tasks (couples deployments and task signatures), direct DB writes (bypasses validation/approvals).
Consequence: polling latency (default 5 s); lease reaper runs every 60 s and on each claim.

### ADR-004 · Accepted · One Result Bundle format (v1.0) with agent-chosen `ref`s
Both agents persist output only via `POST agent/tasks/{id}/results/`. Refs give idempotency and intra-task linking; a bundle is atomic.
Why: one validation/persistence path, safe retries, no client-side UUID bookkeeping.

### ADR-005 · Accepted · Approval gates enforced by backend state machines + content hashes
Agents can only request approvals. Decisions are a user-only endpoint (JWT + DEVELOPER role). Approvals pin a SHA-256 of the reviewed content; messages pin their own hash; sending re-verifies.
Why: "backend must enforce approval, not rely on AI instructions". Approve-then-edit attacks are blocked.

### ADR-006 · Accepted · Approval granularity: SoftwareIdea, ProjectBrief, Campaign (messages via campaign)
One Approval per target. Agent 2 requests brief + campaign approvals separately; UI groups them; launch requires both.
Why: simple, uniform model. Individual messages can be excluded (cancel) before approval.

### ADR-007 · Accepted · Status vocabulary
`UPPER_SNAKE_CASE`, shared `WAITING_FOR_APPROVAL` across reviewables; single definition in `backend/apps/common/enums.py`; OpenAPI enum names pinned (`ENUM_NAME_OVERRIDES`) so generated TS types are stable.

### ADR-008 · Accepted · Outreach v1 = email only, step 1 only, at-most-once
Only `EMAIL` is executable; `sequence_step` must be 1 (follow-ups need reply detection — v2). Message is committed as `SENDING` before the SMTP call, so a crash never double-sends (may leave `SENDING` for manual review).
Transport: workspace SMTP Integration if active, else Django `EMAIL_BACKEND` (console in dev).

### ADR-009 · Accepted · Compliance controls are hard blocks in the send path
Suppression (email/domain/phone), legal basis ≠ UNKNOWN, workspace consent-required countries, lead contactable, sender identity + postal address + opt-out footer, RFC 8058 headers, daily send limit. Configurable by workspace admins; not legal advice.

### ADR-010 · Accepted · Auth: JWT for users, hashed service tokens for agents
SimpleJWT (15 min / 7 d rotating). Frontend keeps tokens in `sessionStorage` (MVP). Agent tokens `agt_<prefix>_<secret>`, SHA-256 at rest, created via `manage.py create_agent_token`.
Superseded in part by ADR-014 (refresh token moved to an httpOnly cookie).

### ADR-011 · Accepted · Secrets
No secrets in code or repo; settings fail fast if missing; test settings generate random keys. Integration secrets Fernet-encrypted with `FIELD_ENCRYPTION_KEY`, write-only in API. LLM/search keys for agents are deployment env vars (agent-owned).

### ADR-012 · Accepted · Contract drift is a CI failure
`docs/openapi.yaml` and `frontend/src/api/schema.d.ts` are generated and committed; CI regenerates and diffs. Migrations checked with `makemigrations --check`.

### ADR-013 · Accepted · Team 3 owns `agents/platform_sdk`
The SDK is integration infrastructure; agent teams consume it and request changes through INTEGRATION_STATUS.

### ADR-014 · Accepted · Browser sessions: access token in memory, refresh token in httpOnly cookie
Login returns only `access` (kept in JS memory, never web storage); the refresh token is an httpOnly, `SameSite=Lax`, `Secure` (non-DEBUG) cookie scoped to `/api/v1/auth/`. Refresh rotates and blacklists the previous token (simplejwt `token_blacklist`); logout and password change/reset revoke tokens.
Why: XSS can no longer exfiltrate a long-lived credential; logout is real. Trade-offs: frontend and API must be same-site (e.g. `app.example.com` + `api.example.com`) and CORS must allow credentials; non-browser API clients use a cookie jar. Breaking for clients that read `refresh` from the login body (only our frontend did).
Settings: `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_SECURE`, `AUTH_THROTTLE_RATE`, `PASSWORD_RESET_TIMEOUT_SECONDS`.

### ADR-015 · Accepted · Inbound email events through one provider-neutral signed webhook
One HMAC-SHA256 (timestamp + body, 5-minute window) endpoint and normalized event format; provider adapters translate. Why: no lock-in to one ESP before one is chosen; suppression logic stays in one place.

### ADR-016 · Accepted · Local Business Finder: polling-derived live events, OpenFreeMap basemap
The Agent 2 dashboard (`/local-finder`) derives the event vocabulary (`research.*`, `business.*`) client-side by diffing REST snapshots (3 s while a task runs, 15 s idle, full refresh 30 s, exponential backoff on errors) and renders a MapLibre GL map (clustered HTML markers) on OpenFreeMap vector tiles (OpenStreetMap data, keyless, commercial use allowed, attribution shown).
Why: polling is the platform's existing live mechanism (no SSE/WebSocket endpoint); the transport is isolated in `features/localFinder/liveFeed.ts`, so a push endpoint can replace it without touching the store or UI. OpenFreeMap needs no key or account. Consequences: up to ~3 s latency; tile host must be allowed by deployment CSP; override with `VITE_MAP_STYLE_URL` (full style) or `VITE_MAP_TILES_URL`/`VITE_MAP_GLYPHS_URL`. The map never positions a business without backend coordinates.

### ADR-017 · Accepted · Frontend visual system: monochrome "deep space" glass, tokens in one file
All styling derives from CSS variables in `frontend/src/style.css` (surfaces `--glass-1/2/3`, lines, text `--ink/--soft/--silver/--muted`, status `--ok/--warn/--bad`, viz ramp, shadows, blur, radii, motion), exposed to Tailwind via `@theme` as semantic utilities (`bg-panel`, `text-silver`, `border-line`, …) and component classes (`.card`, `.glass-nav`, `.glass-pop`, `.btn-*`, `.input`, `.table`, `.chip`, `.segmented`). Colour is reserved for state (ok / warning / error). Inter is self-hosted (`@fontsource-variable/inter`, no third-party font requests). Star background = two canvases painted once per resize + ~20 CSS-twinkling stars; slow drift only on auth pages.
Why: one place to change the look; consistency across pages; no runtime cost from the backdrop (a moving backdrop would force every backdrop-filter to re-blur each frame). Consequences: new UI must use the tokens/classes, not raw palette classes or hex; `--muted` is #80808a (brief asked #71717a) to keep small text ≥ 4.5:1 on glass.


### ADR-018 · Accepted · Country commercial-subject markers are a backend send gate (BG first)
Outreach to a lead whose business `country_code` is in `outreach.services.COMMERCIAL_SUBJECT_MARKERS` must have a subject starting with one of that country's markers (BG: "Търговско предложение" / "Търговско съобщение", case-insensitive). Checked at campaign launch (`409 compliance_blocked`, reason `commercial_subject_marker_missing`) and again per message at send time.
Why: ЗЕТ чл. 6 requires unsolicited commercial e-mail to be identifiable as such; agents add the prefix, but a reviewer edit could drop it, and compliance must not depend on agents (ADR-009). Consequences: the marker text is a conservative **platform convention, not a validated legal reading** — the statute (ДВ бр. 55/2026) was read by the 2026-11-11 Agent 2 session, but whether it prescribes specific wording was not re-confirmed this session (lex.bg fetch failed) and no counsel has reviewed it; have counsel confirm. Agents 1 and 2 prefix BG subjects themselves. Adding a country = one dict entry + test.
