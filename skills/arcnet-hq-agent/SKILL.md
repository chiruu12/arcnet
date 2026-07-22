# ArcNet HQ Agent

Operator maintenance / enhancement agent for ArcNet fleets.

See [`docs/18-hq-agent.md`](../../docs/18-hq-agent.md).

## Intent

Help keep agents working and propose improvements:

1. Check what SigNoz already tracks (`signoz_status`) — reuse dashboards/alerts/Query Range.
2. Prefer HTTP evidence (`signoz_evidence` / Query Range / Case File `links.signoz_trace`) **before** SigNoz MCP — MCP stdio may hang; never block on it.
3. Surface fleet health, session checks, signals, Griffin **MAD** anomalies (not TabFM).
4. Recommend models (exploration) and **propose** changes — never auto-apply.
5. Track agent versions over time so incidents can be pinned to code/model changes.
6. Respect Unplug / prompt-injection defense on untrusted signal text.

## Run locally

```bash
# terminal A — arcnet-server on :8000
# terminal B
PYTHONPATH=sdk:agents uv run python -m hq_agent "summarize fleet + griffin MAD + any proposals"
```

Or in-process:

```python
from hq_agent import build_hq_agent, run_once
from arcnet import init

init(service_name="arcnet-hq-agent", agent_id="hq_agent", exposure="internal")
agent = build_hq_agent()
agent.run("Check agent_j versions and propose gpt-4o if tool_heavy issues")
```

## SDK tools (preferred for coding agents)

```python
from arcnet import hq_tools

hq_tools.signoz_status()
hq_tools.signoz_evidence("s_…")  # prefer HTTP/Query Range over MCP
hq_tools.fleet_overview()
hq_tools.session_check("s_…")
hq_tools.case_file_view("s_…")
hq_tools.replay_compare("s_…")
hq_tools.griffin_anomalies()  # estimator=mad
hq_tools.recommend_models("injection_resist", constraints={"session_id": "s_…"})
hq_tools.propose_model_change("agent_j", "gpt-4o", "S1 resists poorly", from_model="gpt-4o-mini", session_id="s_…")
out = hq_tools.apply_model_change("agent_j", "gpt-4o", "2026-07-22.2", confirm=True)  # human-gated
# out["agentos_reload_required"] is True — restart AgentOS manually
```

## MCP

See [`mcp-tools.json`](mcp-tools.json) + [`mcp_server.py`](mcp_server.py) (JSON-RPC stdio).

## Honesty

- Griffin = **MAD**. TabFM not live. TabPFN needs `TABPFN_TOKEN`.
- Proposals are `signals` with `source=hq_agent` — apply only with `confirm: true`.
