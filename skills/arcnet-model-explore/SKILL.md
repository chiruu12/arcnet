# ArcNet model explore

Exploration-only skill for discovering newer/better models for a task type.
**Does not** mutate live agents, post kill/steer, or run full autonomous ops.

See product plan: [`docs/17-product-rework-plan.md`](../../docs/17-product-rework-plan.md) Phase R3.

## Intent

Periodically (or on demand) recommend candidate models for usages like:

- `tool_heavy` — agents with many tool calls / loops
- `injection_resist` — forward-facing retrieval + side effects
- `cheap_batch` — cost-sensitive internal work
- `long_context` — large transcript / case-file analysis

## SDK (in-process)

```python
from arcnet.model_explore import (
    list_task_types,
    recommend_models,
    fetch_provider_catalog,
    compare_replay_verdicts,
    record_recommendation_note,
)

list_task_types()
rec = recommend_models(
    "injection_resist",
    constraints={"max_cost_usd": 0.1, "session_id": "s_ecfdb55d"},  # TM evidence when present
)
fetch_provider_catalog("openai", live=False)  # curated snapshot; live=True lists OpenAI models only
# compare_replay_verdicts("s_…")  # needs arcnet-server — returns evidence_refs + dimension_winners
record_recommendation_note(task_type="injection_resist", recommendations=rec["recommendations"])
# Optional loop: ARCNET_MODEL_EXPLORE_LOOP=1 → recommend+record note only (never apply/kill)
```

Default Time Machine candidate in HQ is `gpt-4o` (editable). Bound spend: do not call live catalog in loops; snapshot is enough for recommendations.

## MCP tool shapes

See [`mcp-tools.json`](mcp-tools.json). Thin stdio server: [`mcp_server.py`](mcp_server.py).

| Tool | Args | Returns |
|---|---|---|
| `list_task_types` | — | Known usage buckets |
| `recommend_models` | `{task_type, constraints?}` | Ranked `{model, reason, evidence_refs[]}` |
| `compare_replay_verdicts` | `{session_id}` | Dimension winners from Time Machine |
| `fetch_provider_catalog` | `{provider, live?}` | Newest/reliable ids (cached snapshot by default) |

## Status

**R3 thin implementation:** curated OpenAI snapshot + recommend/compare/record helpers + MCP stdio shim. No autonomous fleet; exploration notes only.
