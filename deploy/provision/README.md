# provision/

- `agno-dashboard.json` — official SigNoz Agno dashboard template.
- `dashboard-fleet-ops.json` / `dashboard-threats-trust.json` / `dashboard-cost-tokens.json` — ArcNet custom dashboards (v5 widgets; OpenInference + `arcnet.*` keys from `docs/04`). Threats dashboard includes a ClickHouse SQL panel.
- `alerts.json` — threshold alert rules in **v5 `queries` format** + webhook channel stub. Eval intervals recorded in `meta`.
- `alert-seasonal-anomaly.json` — native seasonal anomaly rule (**screenshot artifact only**; ≥5m windows).
- `setup.py` — validates JSON; with `SIGNOZ_API_KEY` set, POSTs channel + dashboards + rules to SigNoz.

```bash
# validate only (no key)
python deploy/provision/setup.py

# provision when key exists
set -a && source .env && set +a
python deploy/provision/setup.py
```

Manual UI import: Dashboards → Import JSON for each `dashboard-*.json` (+ agno). Alerts → create from `alerts.json` payloads if API provision is skipped.
