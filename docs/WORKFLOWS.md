# Workflows & Status Machines

Enforced in code by `StatusMachineMixin.STATUS_TRANSITIONS` on each model; illegal transitions → `409 invalid_state`.
Values: `backend/apps/common/enums.py`.

## ResearchTask
```
QUEUED ──claim──▶ RUNNING ──complete──▶ COMPLETED
  │                 │  ├──fail(retryable, attempts left) / lease expired──▶ QUEUED
  │                 │  ├──fail / lease expired (attempts exhausted)───────▶ FAILED ──retry (user)──▶ QUEUED
  └─cancel (user)─▶ CANCELLED ◀── fail(code=CANCELLED) | complete | lease expiry  (when cancel_requested)
```
User cancel on RUNNING sets `cancel_requested`; agent sees it in heartbeat, results are refused (`409 cancel_requested`).

## Review lifecycle — SoftwareIdea, ProjectBrief
```
DRAFT ─submit─▶ WAITING_FOR_APPROVAL ─▶ APPROVED ─▶ ARCHIVED
  ▲                    ├─▶ REJECTED ─▶ ARCHIVED
  └──(edit)── CHANGES_REQUESTED ◀─┘ ─submit─▶ WAITING_FOR_APPROVAL
```
Edits (user PATCH or agent re-submission of same `ref`) only in DRAFT / CHANGES_REQUESTED.

## Campaign
```
DRAFT/CHANGES_REQUESTED ─submit─▶ WAITING_FOR_APPROVAL ─▶ APPROVED ─launch─▶ ACTIVE ─▶ COMPLETED
                                         ├─▶ REJECTED              │           ├─pause─▶ PAUSED ─launch─▶ ACTIVE
                                         └─▶ CHANGES_REQUESTED     └─cancel────┴─cancel─▶ CANCELLED
```
Launch additionally requires: linked SoftwareIdea APPROVED (Agent 1), linked ProjectBrief APPROVED (Agent 2), workspace sender identity complete.

## OutreachMessage
```
DRAFT ─(campaign submit)─▶ WAITING_FOR_APPROVAL ─(campaign approved)─▶ APPROVED ─send─▶ SENDING ─▶ SENT
                               ├─(rejected)─▶ REJECTED                    ├─▶ SUPPRESSED      └─▶ FAILED
                               └─(changes)──▶ DRAFT                       ├─▶ FAILED (compliance)
DRAFT/WAITING/APPROVED ─▶ CANCELLED (user exclude) | SUPPRESSED (suppression added)
```
`approved_hash` is set at submit; send refuses if content changed (`content_changed_after_approval`).

## Lead
`NEW → QUALIFIED|DISQUALIFIED → CONTACTED (set by backend on send) → REPLIED → WON|LOST → ARCHIVED`. Agents may update leads only while NEW/QUALIFIED/DISQUALIFIED.

## Opportunity
`NEW ⇄ SHORTLISTED`, `→ DISMISSED → NEW` (user curation).

## Approval
`PENDING → APPROVED | REJECTED | CHANGES_REQUESTED`. One PENDING per target. `content_hash` must match target at decision time (`409 stale_approval`).

| target_type | APPROVED side effects | REJECTED | CHANGES_REQUESTED |
|---|---|---|---|
| SOFTWARE_IDEA | idea APPROVED; auto-create `SAAS_CUSTOMER_RESEARCH` task (`outcome.follow_up_task_id`) | idea REJECTED | idea CHANGES_REQUESTED |
| PROJECT_BRIEF | brief APPROVED | brief REJECTED | brief CHANGES_REQUESTED |
| CAMPAIGN | campaign APPROVED; its WAITING messages → APPROVED | campaign + messages REJECTED | campaign CHANGES_REQUESTED; messages → DRAFT |

Who may decide: human users with role DEVELOPER+ in the workspace. Agents have no route to decisions.

## End-to-end (tested in `tests/integration/test_end_to_end.py`)
1. User creates `SAAS_OPPORTUNITY_RESEARCH` → Agent 1 claims, submits evidence/opportunity/idea → idea WAITING_FOR_APPROVAL.
2. User approves → backend queues `SAAS_CUSTOMER_RESEARCH` → Agent 1 submits businesses/leads/campaign → campaign WAITING_FOR_APPROVAL.
3. Launch before approval → 409. User approves → launches → backend sends with footer → lead CONTACTED → campaign COMPLETED.
4. User creates `LOCAL_LEAD_DISCOVERY` → Agent 2 submits leads + brief + campaign → both WAITING → approved → launched → sent.
5. Recipient clicks unsubscribe → SuppressionEntry (UNSUBSCRIBE_LINK) → future drafts/sends to that address blocked.
