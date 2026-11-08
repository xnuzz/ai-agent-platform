# Agent 2 Contract — Local Business Lead Finder

Owner: Team 2. Agent identifier: **`LOCAL_LEADS`**. Integrate via `agents/platform_sdk` only.
General rules: `API_CONTRACTS.md`.

## Workflow mapping
```
LOCAL_LEAD_DISCOVERY task
  location → businesses → website/technical analysis → problems → qualified leads
  → project brief per qualified lead (submit_for_approval)
  → outreach campaign referencing the brief, prepared in parallel (submit_for_approval)
  ⇒ ProjectBrief + Campaign WAITING_FOR_APPROVAL              [gate, human; shown together per lead]
Both APPROVED ⇒ human launches ⇒ backend sends (launch is blocked until the brief is APPROVED)
```

## Task type `LOCAL_LEAD_DISCOVERY`
Input:
| field | type | default |
|---|---|---|
| `location.city` | str (required) | |
| `location.country_code` | ISO-2 (required, upper-cased) | |
| `location.region` | str | `""` |
| `location.radius_km` | 1–100 | 10 |
| `location.latitude/longitude` | float | — |
| `categories` | [str] ≤30 (e.g. `Dentist`, `Bakery`) | `[]` = any |
| `max_businesses` | 1–200 | 25 |
| `checks` | [problem code] to run | `[]` = all |
| `min_score` | 0–100: qualify threshold | 50 |
| `language` | str | `en` |
| `notes` | str | `""` |

Allowed bundle sections: `evidence`, `businesses`, `leads`, `project_briefs`, `campaigns`.

Expectations:
- Businesses: include `source_data` provider ids (e.g. `{"place_id": …}`) and `evidence_refs` (directory/maps listing). Website scans → `source_type: WEBSITE_SCAN` evidence with the measured facts in `excerpt`/`metadata`.
- Leads: `status` `QUALIFIED` if `score ≥ min_score`, else `DISQUALIFIED` (still submit — useful for dedup and audit). `problems` must cite evidence.
- One `project_brief` per qualified lead: summary, problems, proposed solution, scope items, tech stack, effort (hours) and budget range with currency.
- One campaign per lead (or per batch) with `project_brief_ref`, so the developer approves the project and its outreach together.
- Contacts: prefer generic business addresses; set `legal_basis`; `UNKNOWN` blocks sending.
- Message `body` plain text; no signature/unsubscribe (backend appends). Do not shame the business; describe the issue factually.

## Problem codes (recommended vocabulary; any `UPPER_SNAKE` code is accepted)
`NO_WEBSITE`, `NO_HTTPS`, `SSL_EXPIRED`, `SLOW_PAGE_LOAD`, `NOT_MOBILE_FRIENDLY`, `BROKEN_LINKS`, `OUTDATED_CMS`, `OUTDATED_DESIGN`, `NO_ONLINE_BOOKING`, `NO_CONTACT_FORM`, `POOR_SEO`, `MISSING_META`, `ACCESSIBILITY_ISSUES`, `NO_ANALYTICS`, `SECURITY_HEADERS_MISSING`, `NO_GOOGLE_BUSINESS_PROFILE`.
Adding a code: append here + INTEGRATION_STATUS "Contract changes" (frontend shows codes verbatim).

## Progress stages (recommended)
`PLANNING`, `DISCOVERING_BUSINESSES`, `SCANNING_WEBSITES`, `QUALIFYING`, `WRITING_BRIEFS`, `DRAFTING_OUTREACH`, `SUBMITTING`.

## Compliance notes for discovery
- Respect `robots.txt` and provider ToS; rate-limit scans; identify the crawler with a contact URL in User-Agent (no personal email).
- Collect only data needed for qualification; do not scrape personal social profiles.
- Submit results in batches (e.g. every 10 businesses) so progress is visible and retries are cheap.

Reference payload: `tests/support/bundles.py::local_leads_bundle`.
