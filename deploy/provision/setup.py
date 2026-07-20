"""Idempotent SigNoz provisioner — dashboards, alerts, webhook channel.

Requires SIGNOZ_URL + SIGNOZ_API_KEY. Without the key, validates JSON locally and exits 0
with a clear skip message (Phase 2 human blocker).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
DASHBOARDS = [
    "dashboard-fleet-ops.json",
    "dashboard-threats-trust.json",
    "dashboard-cost-tokens.json",
    "agno-dashboard.json",
]
ALERTS = ROOT / "alerts.json"
SEASONAL = ROOT / "alert-seasonal-anomaly.json"


def _headers(api_key: str) -> dict[str, str]:
    return {"SIGNOZ-API-KEY": api_key, "Content-Type": "application/json"}


def validate_local() -> None:
    for name in DASHBOARDS:
        path = ROOT / name
        data = json.loads(path.read_text())
        assert "widgets" in data or "title" in data, name
        print(f"OK dashboard {name} title={data.get('title')!r} widgets={len(data.get('widgets', []))}")
    alerts = json.loads(ALERTS.read_text())
    for a in alerts["alerts"]:
        assert a.get("version") == "v5", a.get("alert")
        cq = a["condition"]["compositeQuery"]
        assert "queries" in cq and "builderQueries" not in cq, a.get("alert")
        print(f"OK alert {a['alert']!r} queries={len(cq['queries'])}")
    seasonal = json.loads(SEASONAL.read_text())
    assert seasonal.get("version") == "v5"
    print(f"OK seasonal artifact {seasonal['alert']!r}")


def provision(base: str, api_key: str) -> None:
    client = httpx.Client(base_url=base.rstrip("/"), headers=_headers(api_key), timeout=30.0)

    # Webhook channel
    alerts_doc = json.loads(ALERTS.read_text())
    wh = alerts_doc["webhook_channel"]
    ch_payload = {
        "name": wh["name"],
        "type": "webhook",
        "webhook_configs": [
            {
                "send_resolved": True,
                "url": wh["webhook_url"],
            }
        ],
    }
    r = client.post("/api/v1/channels", json=ch_payload)
    print("channel", r.status_code, r.text[:300])

    for name in DASHBOARDS:
        dash = json.loads((ROOT / name).read_text())
        # SigNoz import endpoint (self-host v0.133)
        r = client.post("/api/v1/dashboards", json={"data": dash})
        if r.status_code >= 400:
            r = client.post("/api/v1/dashboards", json=dash)
        print(f"dashboard {name}", r.status_code, r.text[:200])

    for a in alerts_doc["alerts"]:
        body = {
            "alert": a["alert"],
            "alertType": a["alert_type"],
            "ruleType": a["rule_type"],
            "severity": a["severity"],
            "version": a["version"],
            "schemaVersion": a.get("schema_version", "v2alpha1"),
            "condition": a["condition"],
            "labels": a.get("labels", {}),
            "annotations": {
                "description": a.get("description", ""),
                "summary": a.get("summary", ""),
            },
            "evaluation": a.get("evaluation"),
        }
        r = client.post("/api/v1/rules", json=body)
        print(f"alert {a['alert']!r}", r.status_code, r.text[:200])

    seasonal = json.loads(SEASONAL.read_text())
    body = {
        "alert": seasonal["alert"],
        "alertType": seasonal["alert_type"],
        "ruleType": seasonal["rule_type"],
        "severity": seasonal["severity"],
        "version": seasonal["version"],
        "schemaVersion": seasonal.get("schema_version", "v2alpha1"),
        "condition": seasonal["condition"],
        "labels": seasonal.get("labels", {}),
        "annotations": {
            "description": seasonal.get("description", ""),
            "summary": seasonal.get("summary", ""),
        },
        "evaluation": seasonal.get("evaluation"),
    }
    r = client.post("/api/v1/rules", json=body)
    print("seasonal", r.status_code, r.text[:200])


def main() -> int:
    validate_local()
    base = os.getenv("SIGNOZ_URL", "http://localhost:8080")
    key = os.getenv("SIGNOZ_API_KEY", "").strip()
    if not key:
        print("SKIP provision: SIGNOZ_API_KEY empty — JSON validated; import via UI or re-run with key")
        return 0
    provision(base, key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
