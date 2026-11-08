# Agent 2 — Local Business Lead Finder

**Owner: Team 2 (Chat 2).** Team 3 has not implemented anything in this directory — it is reserved for Team 2 (Chat 2).

- Agent identifier: `LOCAL_LEADS` · Task types: `LOCAL_LEAD_DISCOVERY`
- Contract (inputs, result bundle, stages, rules): [`docs/AGENT_2_CONTRACT.md`](../../docs/AGENT_2_CONTRACT.md)
- Integrate ONLY via [`agents/platform_sdk`](../platform_sdk) (`AgentWorker` + `TaskContext`). No direct DB access.
- Executable contract examples that the backend accepts: `tests/support/bundles.py`
- Before changing a shared interface: update docs + `docs/INTEGRATION_STATUS.md`.
