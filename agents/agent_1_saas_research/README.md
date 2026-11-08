# Agent 1 — SaaS Opportunity Research

**Owner: Team 1 (Chat 1).** Team 3 has not implemented anything in this directory — it is reserved for Team 1 (Chat 1).

- Agent identifier: `SAAS_RESEARCH` · Task types: `SAAS_OPPORTUNITY_RESEARCH, SAAS_CUSTOMER_RESEARCH`
- Contract (inputs, result bundle, stages, rules): [`docs/AGENT_1_CONTRACT.md`](../../docs/AGENT_1_CONTRACT.md)
- Integrate ONLY via [`agents/platform_sdk`](../platform_sdk) (`AgentWorker` + `TaskContext`). No direct DB access.
- Executable contract examples that the backend accepts: `tests/support/bundles.py`
- Before changing a shared interface: update docs + `docs/INTEGRATION_STATUS.md`.
