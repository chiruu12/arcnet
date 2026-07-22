"""Idempotent SigNoz provisioner — dashboards, alerts, webhook channel.

Requires SIGNOZ_URL + SIGNOZ_API_KEY. Without the key, validates JSON locally and exits 0
with a clear skip message (Phase 2 human blocker).

Inspect-first: lists existing channels/dashboards/rules by name and skips duplicates.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

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
        assert "preferred_channels" in a or "preferredChannels" in a, a.get("alert")
        print(f"OK alert {a['alert']!r} queries={len(cq['queries'])}")
    seasonal = json.loads(SEASONAL.read_text())
    assert seasonal.get("version") == "v5"
    print(f"OK seasonal artifact {seasonal['alert']!r}")


def _payload(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return None


def _dashboard_title(item: dict[str, Any]) -> str | None:
    data = item.get("data")
    if not isinstance(data, dict):
        return None
    title = data.get("title")
    if isinstance(title, str) and title:
        return title
    nested = data.get("data")
    if isinstance(nested, dict):
        title = nested.get("title")
        if isinstance(title, str) and title:
            return title
    return None


def _list_dashboards(client: httpx.Client) -> list[dict[str, Any]]:
    payload = _payload(client.get("/api/v1/dashboards"))
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", [])
    return data if isinstance(data, list) else []


def _list_rules(client: httpx.Client) -> list[dict[str, Any]]:
    payload = _payload(client.get("/api/v1/rules"))
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", {})
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rules = data.get("rules", [])
        return rules if isinstance(rules, list) else []
    return []


def _list_channels(client: httpx.Client) -> list[dict[str, Any]]:
    payload = _payload(client.get("/api/v1/channels"))
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", [])
    return data if isinstance(data, list) else []


def _rule_body(a: dict[str, Any]) -> dict[str, Any]:
    """Build POST /api/v1/rules body for SigNoz v0.133 (flat condition + preferredChannels)."""
    channels = a.get("preferred_channels") or a.get("preferredChannels") or ["arcnet-webhook"]
    body: dict[str, Any] = {
        "alert": a["alert"],
        "alertType": a["alert_type"],
        "ruleType": a["rule_type"],
        "severity": a["severity"],
        "version": a["version"],
        "condition": a["condition"],
        "labels": a.get("labels", {}),
        "annotations": {
            "description": a.get("description", ""),
            "summary": a.get("summary", ""),
        },
        "preferredChannels": channels,
    }
    if a.get("evaluation"):
        body["evaluation"] = a["evaluation"]
    return body


def provision(base: str, api_key: str) -> None:
    client = httpx.Client(base_url=base.rstrip("/"), headers=_headers(api_key), timeout=30.0)

    channels = _list_channels(client)
    existing_channels = {c.get("name") for c in channels if isinstance(c.get("name"), str)}
    print(f"inspect channels={sorted(existing_channels)}")

    dashes = _list_dashboards(client)
    title_to_ids: dict[str, list[str]] = {}
    for d in dashes:
        title = _dashboard_title(d)
        did = d.get("id")
        if title and isinstance(did, str):
            title_to_ids.setdefault(title, []).append(did)
    # Keep first of each title; delete duplicates from prior non-idempotent runs
    for title, ids in sorted(title_to_ids.items()):
        if len(ids) > 1:
            for extra in ids[1:]:
                r = client.delete(f"/api/v1/dashboards/{extra}")
                print(f"dedupe dashboard title={title!r} id={extra[:8]}…", r.status_code)
            title_to_ids[title] = [ids[0]]
    existing_dash_titles = set(title_to_ids)
    print(f"inspect dashboards={sorted(existing_dash_titles)}")

    rules = _list_rules(client)
    existing_alerts = {r.get("alert") for r in rules if isinstance(r.get("alert"), str)}
    # Drop ephemeral probe rules from debugging
    for r in rules:
        name = r.get("alert")
        rid = r.get("id")
        if (
            isinstance(name, str)
            and isinstance(rid, str)
            and (name.startswith("arcnet probe") or name.startswith("arcnet seasonal probe"))
        ):
            dr = client.delete(f"/api/v1/rules/{rid}")
            print(f"cleanup probe rule {name!r}", dr.status_code)
            existing_alerts.discard(name)
    print(f"inspect rules={sorted(a for a in existing_alerts if a)[:12]} count={len(existing_alerts)}")

    alerts_doc = json.loads(ALERTS.read_text())
    wh = alerts_doc["webhook_channel"]
    if wh["name"] in existing_channels:
        print(f"SKIP channel {wh['name']!r} (exists)")
    else:
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
        title = dash.get("title") or name
        if title in existing_dash_titles:
            print(f"SKIP dashboard {name} title={title!r} (exists)")
            continue
        r = client.post("/api/v1/dashboards", json={"data": dash})
        if r.status_code >= 400:
            r = client.post("/api/v1/dashboards", json=dash)
        print(f"dashboard {name}", r.status_code, r.text[:200])
        if r.status_code < 400:
            existing_dash_titles.add(title)

    def _post_rule(a: dict[str, Any], label: str) -> None:
        alert_name = a["alert"]
        if alert_name in existing_alerts:
            print(f"SKIP {label} {alert_name!r} (exists)")
            return
        body = _rule_body(a)
        r = client.post("/api/v1/rules", json=body)
        print(f"{label} {alert_name!r}", r.status_code, r.text[:200])
        if r.status_code < 400:
            existing_alerts.add(alert_name)

    for a in alerts_doc["alerts"]:
        _post_rule(a, "alert")

    seasonal = json.loads(SEASONAL.read_text())
    _post_rule(seasonal, "seasonal")


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
