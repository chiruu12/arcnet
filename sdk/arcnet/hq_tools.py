"""HQ Agent callable tools — HTTP/SDK client over ArcNet APIs (docs/18).

Bounded envelopes only. Does not import agents/ or scripts/.
Griffin anomalies are labeled MAD (TabFM not live; TabPFN optional later).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from arcnet.hq import check_session, signals_view
from arcnet.model_explore import recommend_models as _recommend_models

_DEFAULT_BASE = "http://localhost:8000"


def _base(server_url: str | None = None) -> str:
    return (server_url or os.getenv("ARCNET_SERVER_URL") or _DEFAULT_BASE).rstrip("/")


def _get(path: str, *, server_url: str | None = None, timeout: float = 10.0) -> Any:
    url = f"{_base(server_url)}{path}"
    with httpx.Client(timeout=timeout) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def _post(
    path: str,
    body: dict[str, Any],
    *,
    server_url: str | None = None,
    timeout: float = 10.0,
) -> Any:
    url = f"{_base(server_url)}{path}"
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=body)
        r.raise_for_status()
        return r.json()


def signoz_status(*, server_url: str | None = None) -> dict[str, Any]:
    """What SigNoz is tracking from ArcNet's probe — status + dashboard UUIDs."""
    return _get("/api/signoz/status", server_url=server_url)


def fleet_overview(*, server_url: str | None = None) -> list[dict[str, Any]]:
    return _get("/api/fleet", server_url=server_url)


def agent_signals(
    agent_or_session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    return signals_view(agent_or_session_id, server_url=server_url)


def session_check(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    return check_session(session_id, server_url=server_url)


def griffin_anomalies(*, server_url: str | None = None) -> dict[str, Any]:
    """Griffin cache + recent griffin-sourced signals. Estimator = MAD (honest)."""
    status = _get("/api/griffin/status", server_url=server_url)
    signals = _get("/api/signals?limit=50&offset=0", server_url=server_url)
    griffin_sigs = [
        s
        for s in (signals if isinstance(signals, list) else [])
        if isinstance(s, dict) and str(s.get("source") or "").lower() == "griffin"
    ][:20]
    return {
        "estimator": "mad",
        "note": "Griffin uses MAD (median/MAD robust z-score). TabFM too slow; TabPFN needs TABPFN_TOKEN.",
        "status": status,
        "recent_griffin_signals": griffin_sigs,
    }


def list_agent_models(
    agent_id: str,
    *,
    server_url: str | None = None,
) -> list[dict[str, Any]]:
    return _get(f"/api/agents/{agent_id}/models", server_url=server_url)


def recommend_models(
    task_type: str,
    *,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Exploration-only model ranking (local curated catalog)."""
    return _recommend_models(task_type, constraints=constraints)


def agent_version_timeline(
    agent_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    return _get(f"/api/agents/{agent_id}/versions/timeline", server_url=server_url)


def register_agent_version(
    agent_id: str,
    version: str,
    *,
    model: str | None = None,
    model_version: str | None = None,
    source_ref: str | None = None,
    notes: str | None = None,
    server_url: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"version": version}
    if model is not None:
        body["model"] = model
    if model_version is not None:
        body["model_version"] = model_version
    if source_ref is not None:
        body["source_ref"] = source_ref
    if notes is not None:
        body["notes"] = notes
    return _post(f"/api/agents/{agent_id}/versions", body, server_url=server_url)


def propose_model_change(
    agent_id: str,
    to_model: str,
    reason: str,
    *,
    from_model: str | None = None,
    task_type: str | None = None,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Record a proposal note — does not mutate live agent config."""
    from_bit = f"{from_model} → " if from_model else ""
    guidance = (
        f"Proposed model change for {agent_id}: {from_bit}{to_model}."
        + (f" task_type={task_type}." if task_type else "")
        + " Apply manually (register_agent_version after deploy). No auto-apply."
    )
    return _post(
        "/api/signal",
        {
            "agent_id": agent_id,
            "kind": "note",
            "severity": "info",
            "reason": reason[:500],
            "guidance": guidance[:800],
            "source": "hq_agent",
        },
        server_url=server_url,
    )


def list_model_proposals(
    *,
    agent_id: str | None = None,
    server_url: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    q = f"/api/signals?limit={limit}&offset=0"
    if agent_id:
        q += f"&agent_id={agent_id}"
    rows = _get(q, server_url=server_url)
    if not isinstance(rows, list):
        return []
    return [
        r
        for r in rows
        if isinstance(r, dict) and str(r.get("source") or "").lower() == "hq_agent"
    ]
