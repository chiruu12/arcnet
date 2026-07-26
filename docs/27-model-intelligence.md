# 27 — Model intelligence

Static catalog + evidence-grounded cost / reasoning recommendations for observed agents.

**Routes:**
- `GET /api/agents/{agent_id}/model-intel` — bucketed recommendations + projections
- `GET /api/models/catalog` — filtered catalog export (additive)

The cascade list stays on `GET /api/agents/{agent_id}/models` unchanged (see `docs/12`).

## Catalog schema v2 (`2026-07e`)

- Module: `server/arcnet_server/model_catalog.py`
- `CATALOG_VERSION = "2026-07e"`. Bump when refreshing rows or list prices.
- Per model: `id`, `provider`, `display_name`, `capability_tier` (`frontier` / `high` / `mid` / `light`), `cost_class` (`premium` / `standard` / `economy`), `input_usd_per_mtok`, `cached_input_usd_per_mtok`, `output_usd_per_mtok`, optional `long_context` tier, `context_window`, `max_output_tokens`, `reasoning`, `reasoning_control`, `status` (`current` / `preview` / `legacy` / `deprecated`), `released`, `knowledge_cutoff`, `strengths`, `caveats[]`, `source_url`, `price_verified`.
- **2026-07e additions** (also in `CATALOG_HIGHLIGHT_IDS`): `kimi-k2.7-code`, `kimi-k3` (API preview), `qwen3.8-max-preview`, `qwen3.6-35b-a3b`, `deepseek-v4-flash`, `deepseek-v4-pro`.
- `GET /api/agents/{id}/model-intel` includes `catalog_highlights[]` — non-current candidates whose ids are in `CATALOG_HIGHLIGHT_IDS` (HQ “new in catalog”). Other preview models stay in recommendation buckets only.
- Agent-oriented GETs accept `?format=toon` (default `json`) — see `docs/12-data-api.md`.
- Legacy rows (`legacy-baseline-v1`, `gpt-4o`, `o4-mini`, …) remain for hero replay pricing — excluded from active recommendation buckets.
- SDK live-run costing (`sdk/arcnet/pricing.py`) maps bare Anthropic catalog ids to dated API slugs via `CATALOG_ID_ALIASES`.
- HQ Agent + SDK explore fetch `GET /api/models/catalog` over HTTP; curated snapshot is offline fallback.

### Update cadence

1. When providers publish new list prices or model ids, edit `MODELS` and bump `CATALOG_VERSION`.
2. Keep integrity checks green (`catalog_integrity_errors()` / `server/tests/test_model_intelligence.py`).
3. Do **not** scrape live provider APIs inside the server path for pricing (offline-safe).

## How projections are computed

1. **Usage evidence** (SQLite only): sum `usage.input_tokens` / `usage.output_tokens` across sessions.
2. **Baseline cost**: catalog rates for `agents.model` × token totals. Unknown model → `baseline_projected_cost_usd = null`.
3. **Per candidate**: same token totals × catalog rates → `projected_cost_usd` and `projected_cost_usd_cached` (cached-input rate).
4. **`projected_cost_delta`** = candidate − baseline (null when baseline unknown).

Formula (USD):

```
cost = (input_tokens / 1e6) * input_usd_per_mtok
     + (output_tokens / 1e6) * output_usd_per_mtok
```

Use `cached_input_usd_per_mtok` when projecting stable-prompt workloads.

## Recommendation buckets

Candidates (except current) are assigned:

| Bucket | Meaning |
|--------|---------|
| `recommended_upgrade` | Higher `capability_tier`, fit score justified by recorded workload |
| `cost_saver` | Same-or-adequate capability at lower projected spend |
| `peer` | Same tier, lateral move |
| `not_advised` | Legacy/deprecated, catalog caveats, or blockers (e.g. context too small) |

Each candidate carries `fit: { score, reasons[], blockers[] }` citing recorded evidence. Legacy rows never appear in upgrade buckets ahead of `current` models.

Sorting: current first, then bucket order, then fit score (desc), then status rank.

## Reasoning recommendation

Set only when **recorded** workload looks hard / adversarial:

- `threats_per_session ≥ 0.25` with ≥1 threat, and/or
- ≥1 contested replay verdict (`regressed`, `mixed`, `improved`, `inconclusive`).

Returns structured `evidence[]` entries plus `threats_per_session` and `threat_session_rate`. Suggests from `status: current` reasoning models only (default `gpt-5.6-terra`).

## Honesty caveats

- Catalog dollars are **list-price estimates**, not your bill.
- Token totals are only as complete as session `usage` rows.
- Delta is “same recorded tokens, different list price,” not a quality/latency prediction.
- Product core (`server/`) owns the catalog; `agents/` / `scripts/` must not be imported by server.

## HQ surface

`hq/src/views/HqAgent.tsx` renders `catalog_highlights` under “new in catalog”, then full recommendation buckets (no silent row cap) with input/cached/output price columns, capability vs cost class chips, preview chips, legacy styling, and `price_verified` dates. Agent_view mode shows TOON panels (`model_intel.toon` / `model_proposals.toon`).
