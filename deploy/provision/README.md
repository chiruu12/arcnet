# provision/

- `agno-dashboard.json` — official SigNoz Agno dashboard template.
- `dashboard-fleet-ops.json` / `dashboard-threats-trust.json` / `dashboard-cost-tokens.json` — ArcNet custom dashboards (v5 widgets; OpenInference + `arcnet.*` keys from `docs/04`). Threats dashboard includes a ClickHouse SQL panel.
- `alerts.json` — threshold alert rules in **v5 `queries` format** + webhook channel stub. Eval intervals recorded in `meta`. On SigNoz `v0.133`, `POST /api/v1/rules` wants the **flat** condition (`op`/`matchType` numeric codes + `preferredChannels`); nested `thresholds.spec` is rejected.
- `alert-seasonal-anomaly.json` — native seasonal anomaly rule (**screenshot artifact only**; ≥5m windows).
- `setup.py` — validates JSON; with `SIGNOZ_API_KEY` set, inspect-first POSTs channel + dashboards + rules (skips existing names; dedupes duplicate titles only for ArcNet/Agno dashboards this script ships). Exact ephemeral probe alert names are cleaned by default; pass `--cleanup-probes` for prefix cleanup.

```bash
# validate only (no key)
python deploy/provision/setup.py

# provision when key exists
set -a && source .env && set +a
python deploy/provision/setup.py

# optional: also delete leftover 'arcnet probe*' / 'arcnet seasonal probe*' prefix rules
python deploy/provision/setup.py --cleanup-probes
```

Manual UI import: Dashboards → Import JSON for each `dashboard-*.json` (+ agno). Alerts → create from `alerts.json` payloads if API provision is skipped.
