# platform_sdk (owned by Team 3)

Supported client for agents → backend. Implements `docs/API_CONTRACTS.md §Agent API` exactly.

```python
from platform_sdk import AgentWorker, PlatformClient, new_bundle

def research(ctx):
    ctx.progress(10, stage="SEARCHING", message="Searching sources")
    bundle = new_bundle()
    bundle["evidence"].append({"ref": "ev1", "url": "https://...", "source_type": "FORUM", "excerpt": "..."})
    bundle["opportunities"].append({"ref": "op1", "title": "...", "problem_statement": "...", "evidence_refs": ["ev1"]})
    bundle["software_ideas"].append({"ref": "idea1", "opportunity_ref": "op1", "name": "...", "summary": "...",
                                     "evidence_refs": ["ev1"], "submit_for_approval": True})
    report = ctx.submit(bundle)          # report["refs"]["software_ideas"]["idea1"] -> backend UUID
    return {"ideas": 1}                  # stored as task.result_summary

AgentWorker(PlatformClient.from_env(), {"SAAS_OPPORTUNITY_RESEARCH": research}).run_forever()
```

Env: `PLATFORM_API_URL` (e.g. `http://backend:8000`), `PLATFORM_AGENT_TOKEN` (from `manage.py create_agent_token`).

Install: `pip install -e agents/platform_sdk`.
