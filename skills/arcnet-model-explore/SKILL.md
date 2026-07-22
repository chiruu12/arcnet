# ArcNet model explore (scaffold)

Exploration-only skill for discovering newer/better models for a task type.
**Does not** mutate live agents, post kill/steer, or run full autonomous ops.

See product plan: [`docs/17-product-rework-plan.md`](../../docs/17-product-rework-plan.md) Phase R3.

## Intent

Periodically (or on demand) recommend candidate models for usages like:

- `tool_heavy` — agents with many tool calls / loops
- `injection_resist` — forward-facing retrieval + side effects
- `cheap_batch` — cost-sensitive internal work
- `long_context` — large transcript / case-file analysis

## MCP tool shapes (target — not wired yet)

| Tool | Args | Returns |
|---|---|---|
| `list_task_types` | — | Known usage buckets |
| `recommend_models` | `{task_type, constraints?}` | Ranked `{model, reason, evidence_refs[]}` |
| `compare_replay_verdicts` | `{session_id}` | Dimension winners from Time Machine |
| `fetch_provider_catalog` | `{provider}` | Cached newest/reliable ids |

## Status

**Scaffold only.** No live catalog crawler in this PR. Prefer ArcNet API foundations + HQ cascade (R1/R2) over half-built explorers.
