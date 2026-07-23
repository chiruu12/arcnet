# 27 — Model intelligence

Static catalog + evidence-grounded cost / reasoning recommendations for observed agents.

**Route:** `GET /api/agents/{agent_id}/model-intel` (additive endpoint; the cascade list stays on `GET /api/agents/{agent_id}/models` unchanged; see `docs/12`).

## Catalog

- Module: `server/arcnet_server/model_catalog.py`
- `CATALOG_VERSION = "2026-07"` (YYYY-MM). Bump when refreshing rows or list prices.
- Coverage (2026-07): OpenAI GPT-5-class + o-series, Anthropic Opus-4.8 / Sonnet / Haiku, Google Gemini-3-class, Moonshot Kimi K3, xAI Grok-4.5-class.
- Per model: `id`, `provider`, `tier` ∈ `{frontier_reasoning, reasoning, standard, fast}`, `input_usd_per_mtok`, `output_usd_per_mtok`, `context_window`, `reasoning` (bool), one-line `strengths`.
- Every price carries **`catalog list-price estimate as of {CATALOG_VERSION}`** — never present as measured invoices or live provider quotes.
- SDK live-run costing (`sdk/arcnet/pricing.py`) maps bare Anthropic catalog ids to dated API slugs via `CATALOG_ID_ALIASES` (e.g. `claude-sonnet-5` → `claude-sonnet-4-5-20250929`).

### Update cadence

1. When providers publish new list prices or model ids, edit `MODELS` and set `CATALOG_VERSION` to the month of the edit.
2. Keep integrity checks green (`catalog_integrity_errors()` / `server/tests/test_model_intelligence.py`).
3. Do **not** scrape live provider APIs inside the server path for pricing (no new deps; offline-safe).

## How projections are computed

1. **Usage evidence** (SQLite only): for the agent, sum `usage.input_tokens` / `usage.output_tokens` across sessions (aliases: `prompt_tokens` / `completion_tokens`). If only `total_tokens` / `tokens` is present, split 50/50 so both rates still apply. Counts and session totals are returned as `usage_evidence`.
2. **Baseline cost**: catalog rates for `agents.model` × those token totals. Unknown current model → `baseline_projected_cost_usd = null`.
3. **Per candidate**: same token totals × that candidate's catalog rates → `projected_cost_usd`.  
   `projected_cost_delta = projected_cost_usd − baseline` (null when baseline unknown).
4. **No other sources**: no synthetic benchmarks, no cross-tenant averages, no guessed tokens.

Formula (USD):

```
cost = (input_tokens / 1e6) * input_usd_per_mtok
     + (output_tokens / 1e6) * output_usd_per_mtok
```

## Reasoning recommendation

`reasoning_recommendation` is set only when **recorded** workload looks hard / adversarial:

- `threat_rate = threats_for_agent / sessions_for_agent` ≥ `0.25` with ≥1 threat, and/or
- ≥1 replay on this agent's sessions whose verdict name is in `{regressed, mixed, improved, inconclusive}` (contested Time Machine outcomes).

Rationale text **cites those recorded numbers** (counts and rates). Suggested model is a catalog reasoning-tier id (default `o4-mini` when present). Clean agents get `null` — no speculative upgrade pitch.

## Honesty caveats

- Catalog dollars are **list-price estimates**, not your bill.
- Token totals are only as complete as session `usage` rows; missing usage → zero tokens → zero projected spend (still honest).
- Delta is “same recorded tokens, different list price,” not a prediction of quality, latency, or refusal rates.
- Reasoning rec is a **workload heuristic on DB counts**, not a published eval scoreboard.
- Product core (`server/`) owns the catalog; `agents/` / `scripts/` must not be imported by server. HQ cascade clients keep reading `GET /api/agents/{agent_id}/models` (bare list); the intel object repeats that list under `models` for one-fetch consumers.

## HQ surface

`hq/src/views/HqAgent.tsx` shows catalog version, tier, projected cost delta, and the reasoning recommendation inside the existing agent page — no redesign.
