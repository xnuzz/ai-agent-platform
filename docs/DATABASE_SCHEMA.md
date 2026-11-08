# Database Schema (canonical entities)

PostgreSQL 16. All PKs are UUID v4 (except `ResultRef`). All business tables have `workspace_id`, `created_at`, `updated_at`.
Source of truth for fields: the Django models (`backend/apps/*/models.py`) and `docs/openapi.yaml`. This file documents ownership, relationships and rules. Status lifecycles: `WORKFLOWS.md`.

## Ownership
Only the backend writes these tables. "Producer" = who supplies the data (via API).

| Entity | App | Producer | Key relationships | Uniqueness / validation |
|---|---|---|---|---|
| **User** | accounts | user signup | memberships | email unique (lower-cased); password validators (min 10) |
| **Workspace** | accounts | user | tenant root; sender identity; `consent_required_countries` (ISO-2 list); `daily_send_limit` | slug unique |
| Membership | accounts | admin | user ↔ workspace, `role` | (user, workspace) unique; ≥1 OWNER kept |
| **ResearchTask** | orchestration | user / backend (auto follow-up) | `parent_task`, `software_idea` (customer research), `claimed_token` | `input` validated per `task_type`; `agent` derived from `task_type` |
| AgentToken | orchestration | ops (`create_agent_token`) | — | `prefix` unique; only SHA-256 of key stored |
| ResultRef | orchestration | backend | (task, kind, ref) → object UUID | unique (task, kind, ref) — idempotency |
| **Evidence** | research | agents | `research_task`; M2M from Opportunity, SoftwareIdea, Business, Lead, ProjectBrief | url ≤2000, excerpt ≤5000 |
| **Opportunity** | research | Agent 1 | `research_task`, evidence | score 0–100, pain_severity 1–5 |
| **SoftwareIdea** | research | Agent 1 (edits: user) | `opportunity`, evidence; leads, campaigns, customer tasks | score 0–100; editable only DRAFT/CHANGES_REQUESTED |
| **Business** | leads | Agent 1 & 2 | evidence, `first_seen_task` | unique (workspace, `dedupe_key`): `domain:<host>` else `name:<norm>|<city>|<CC>` |
| **Lead** | leads | Agent 1 & 2 | `business`, `software_idea` (Agent 1 only), `research_task`, evidence | unique (workspace, business, source, software_idea) NULLS NOT DISTINCT; `problems` JSON (see AGENT_2_CONTRACT) |
| **ProjectBrief** | leads | Agent 2 (edits: user) | `lead`, evidence | editable only DRAFT/CHANGES_REQUESTED |
| **Campaign** | outreach | Agent 1 & 2 | `software_idea` (A1) or `project_brief` (A2, optional), messages | editable only DRAFT/CHANGES_REQUESTED |
| **OutreachMessage** | outreach | Agent 1 & 2 | `campaign`, `lead` | unique (campaign, lead, sequence_step); `approved_hash` pins approved content; `to_email` snapshotted from lead |
| **Approval** | approvals | agent or user requests; user decides | `target_type` + `target_id`, `research_task` | max one PENDING per target (partial unique index); `content_hash`, `snapshot` |
| **SuppressionEntry** | outreach | user / unsubscribe link / system | — | unique (workspace, type, normalized value) |
| **Integration** | integrations | admin | — | `config` must not contain secret-like keys; `secret_encrypted` Fernet |
| **AuditEvent** | audit | backend | actor_user / actor_agent, target_type+id | append-only (save/delete raise) |

`Lead.source` / `Campaign.source`: `SAAS_RESEARCH` | `LOCAL_LEADS` | `MANUAL`.

## Personal data (GDPR)
Personal data lives only in: `User`, `Lead.contact_*`, `OutreachMessage.to_email`, `SuppressionEntry.value` (EMAIL/PHONE), `AuditEvent.ip_address`. `Business` holds public business data. Agents should prefer `GENERIC_BUSINESS` addresses and record `legal_basis` + `legal_basis_note` per lead.
Retention/erasure tooling is **not implemented yet** (see INTEGRATION_STATUS). Suppression entries must be kept on erasure (that is their purpose).

## Migration rules
- Only Team 3 creates migrations for `backend/`. Agent teams request schema changes via `INTEGRATION_STATUS.md` → "Requests to Team 3".
- CI fails if models change without a migration (`makemigrations --check`).
