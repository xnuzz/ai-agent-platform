# Agent 1 Contract — SaaS Opportunity Research

Owner: Team 1. Agent identifier: **`SAAS_RESEARCH`**. Integrate via `agents/platform_sdk` only.
General rules (auth, lease, bundle format, errors): `API_CONTRACTS.md`.

## Workflow mapping
```
SAAS_OPPORTUNITY_RESEARCH task
  research industry → problems (opportunities) → software ideas (submit_for_approval)
  ⇒ SoftwareIdea WAITING_FOR_APPROVAL                         [gate 1, human]
APPROVED ⇒ backend auto-creates SAAS_CUSTOMER_RESEARCH task (unless decision options.auto_continue=false)
SAAS_CUSTOMER_RESEARCH task
  potential customers (businesses + leads) → offer → outreach drafts (campaign, submit_for_approval)
  ⇒ Campaign WAITING_FOR_APPROVAL                             [gate 2, human]
APPROVED ⇒ human launches ⇒ backend sends (Agent 1 never sends)
```

## Task type `SAAS_OPPORTUNITY_RESEARCH`
Input (validated by backend; defaults applied before you receive it):
| field | type | default |
|---|---|---|
| `industry` | str ≤200 (required) | |
| `regions` | [ISO-3166 alpha-2] | `[]` = global |
| `keywords` | [str] ≤20 | `[]` |
| `customer_segment` | `SMB`/`MID_MARKET`/`ENTERPRISE`/`ANY` | `ANY` |
| `max_opportunities` | 1–20 | 5 |
| `max_ideas` | 1–10 | 3 |
| `language` | str | `en` |
| `notes` | str ≤2000 | `""` |

Allowed bundle sections: `evidence`, `opportunities`, `software_ideas`.
Expectations:
- Every opportunity and idea cites ≥1 evidence item (`evidence_refs`). Evidence = real, retrievable sources (`url`, `source_type`, short `excerpt` quote, `retrieved_at`). No fabricated URLs.
- `competitors` list on opportunities: `{name, url, notes}`.
- Ideas link `opportunity_ref`. Set `submit_for_approval: true` on ideas you recommend, with an `approval_summary` (why, risks) — this is what the developer reads first.
- Respect `max_opportunities` / `max_ideas`.

## Task type `SAAS_CUSTOMER_RESEARCH`
Created by the backend after idea approval (or manually). Input:
| field | type | default |
|---|---|---|
| `software_idea_id` | UUID of an APPROVED idea (required) | |
| `regions` | [ISO-2] | `[]` |
| `max_leads` | 1–200 | 25 |
| `channels` | [`EMAIL`] | `["EMAIL"]` |
| `language` | str | `en` |
| `notes` | str | `""` |

`task.context.software_idea` (+ `context.opportunity`) contain the approved idea — use it; do not re-research the idea.
Allowed sections: `evidence`, `businesses`, `leads`, `campaigns`. Leads are automatically linked to the task's software idea (`source=SAAS_RESEARCH`).
Expectations:
- One campaign per task is typical: `offer` = sales offer (headline, value proposition, pricing, CTA); one message per lead (`sequence_step: 1`).
- Prefer `GENERIC_BUSINESS` contact emails. Set `contact.legal_basis` honestly; `UNKNOWN` ⇒ backend will refuse to send to that lead.
- Call `ctx.check_suppression(emails=[…])` before drafting; suppressed recipients are skipped anyway.
- Message `body`: plain text, no signature/unsubscribe (backend appends). No false claims, no fake urgency, no impersonation.

## Progress stages (`heartbeat.stage`, free text ≤60; recommended values for the dashboard)
`PLANNING`, `SEARCHING`, `ANALYZING_COMPETITORS`, `SCORING`, `GENERATING_IDEAS`, `FINDING_CUSTOMERS`, `DRAFTING_OUTREACH`, `SUBMITTING`.

## Failure codes (`fail.code`)
`CANCELLED` (after `TaskCancelled`), `retryable_error` (+`retryable: true`) for rate limits/outages, `agent_error` for bugs, `invalid_input` for inputs you can't act on (raise `platform_sdk.InvalidInputError`). SDK maps exceptions automatically.

## Minimal handler
```python
from platform_sdk import AgentWorker, PlatformClient, new_bundle

def opportunity_research(ctx):
    ctx.progress(5, stage="PLANNING")
    b = new_bundle()
    # ... research with your LLM/search adapters, fill b["evidence"], b["opportunities"], b["software_ideas"]
    report = ctx.submit(b)
    return {"opportunities": len(b["opportunities"]), "ideas": len(b["software_ideas"])}

AgentWorker(PlatformClient.from_env(), {
    "SAAS_OPPORTUNITY_RESEARCH": opportunity_research,
    "SAAS_CUSTOMER_RESEARCH": customer_research,
}).run_forever()
```
Reference payloads: `tests/support/bundles.py::opportunity_bundle`, `customer_bundle`.
