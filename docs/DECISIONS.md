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
Follow-up: move refresh token to httpOnly cookie before production (INTEGRATION_STATUS).

### ADR-011 · Accepted · Secrets
No secrets in code or repo; settings fail fast if missing; test settings generate random keys. Integration secrets Fernet-encrypted with `FIELD_ENCRYPTION_KEY`, write-only in API. LLM/search keys for agents are deployment env vars (agent-owned).

### ADR-012 · Accepted · Contract drift is a CI failure
`docs/openapi.yaml` and `frontend/src/api/schema.d.ts` are generated and committed; CI regenerates and diffs. Migrations checked with `makemigrations --check`.

### ADR-013 · Accepted · Team 3 owns `agents/platform_sdk`
The SDK is integration infrastructure; agent teams consume it and request changes through INTEGRATION_STATUS.
