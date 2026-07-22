"""HQ Agent callable tools — HTTP/SDK client over ArcNet APIs (docs/18).

Bounded envelopes only. Does not import agents/ or scripts/.
Griffin anomalies are labeled MAD (TabFM not live; TabPFN optional later).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from arcnet.hq import check_session, incident_view, signals_view
from arcnet.model_explore import compare_replay_verdicts as _compare_replay_verdicts
from arcnet.model_explore import recommend_models as _recommend_models

_DEFAULT_BASE = "http://localhost:8000"


def _base(server_url: str | None = None) -> str:
    return (server_url or os.getenv("ARCNET_SERVER_URL") or _DEFAULT_BASE).rstrip("/")


def _get(path: str, *, server_url: str | None = None, timeout: float = 10.0) -> Any:
    url = f"{_base(server_url)}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        return {"error": "timeout", "path": path, "timeout_s": timeout}
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.text[:300]
        except Exception:  # noqa: BLE001
            detail = str(exc)
        return {
            "error": "http_error",
            "path": path,
            "status": exc.response.status_code,
            "detail": detail,
        }
    except httpx.HTTPError as exc:
        return {"error": "transport_error", "path": path, "detail": str(exc)[:300]}


def _post(
    path: str,
    body: dict[str, Any],
    *,
    server_url: str | None = None,
    timeout: float = 10.0,
) -> Any:
    url = f"{_base(server_url)}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        return {"error": "timeout", "path": path, "timeout_s": timeout}
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.text[:300]
        except Exception:  # noqa: BLE001
            detail = str(exc)
        return {
            "error": "http_error",
            "path": path,
            "status": exc.response.status_code,
            "detail": detail,
        }
    except httpx.HTTPError as exc:
        return {"error": "transport_error", "path": path, "detail": str(exc)[:300]}


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
    """Compact check envelope — prefer version_pinpoint.narrative for change attribution."""
    try:
        out = check_session(session_id, server_url=server_url)
    except Exception as exc:  # noqa: BLE001
        return {"error": "check_failed", "session_id": session_id, "detail": str(exc)[:300]}
    if isinstance(out, dict):
        data = out.get("data") if isinstance(out.get("data"), dict) else out
        pin = (data or {}).get("version_pinpoint") if isinstance(data, dict) else None
        if isinstance(pin, dict) and pin.get("narrative"):
            out = dict(out)
            out["pinpoint_hint"] = pin["narrative"]
            related = (data or {}).get("related_views") if isinstance(data, dict) else None
            if isinstance(related, dict):
                out["evidence_pointers"] = {k: v for k, v in related.items() if v}
    return out


def case_file_view(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Bounded Case File / incident envelope (no zip, no full tool dumps)."""
    return incident_view(session_id, server_url=server_url)


def replay_compare(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Bounded Time Machine verdict summaries for a session."""
    return _compare_replay_verdicts(session_id, server_url=server_url)


def griffin_anomalies(*, server_url: str | None = None) -> dict[str, Any]:
    """Griffin cache + recent griffin-sourced signals. Estimator = MAD (honest)."""
    status = _get("/api/griffin/status", server_url=server_url)
    signals = _get("/api/signals?source=griffin&limit=20&offset=0", server_url=server_url)
    griffin_sigs = [s for s in (signals if isinstance(signals, list) else []) if isinstance(s, dict)]
    return {
        "estimator": "mad",
        "note": "Griffin uses MAD (median/MAD robust z-score). TabFM too slow; TabPFN needs TABPFN_TOKEN.",
        "status": status,
        "recent_griffin_signals": griffin_sigs[:20],
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
    """Exploration-only ranking. Live OpenAI list when OPENAI_API_KEY set (or constraints.live)."""
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
    session_id: str | None = None,
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
    if session_id is not None:
        body["session_id"] = session_id
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
        + " Apply via POST /api/agents/{id}/apply-model with confirm:true (human-gated)."
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
    # Filter at the API so newer non-hq_agent signals cannot hide proposals.
    q = f"/api/signals?source=hq_agent&limit={limit}&offset=0"
    if agent_id:
        q += f"&agent_id={agent_id}"
    rows = _get(q, server_url=server_url)
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def apply_model_change(
    agent_id: str,
    model: str,
    version: str,
    *,
    confirm: bool = False,
    model_version: str | None = None,
    source_ref: str | None = None,
    notes: str | None = None,
    session_id: str | None = None,
    proposal_signal_id: str | None = None,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Human-gated apply — requires confirm=True; records version bump on the server."""
    if confirm is not True:
        return {
            "applied": False,
            "error": "confirm=True required (human-gated; refusing silent apply)",
        }
    body: dict[str, Any] = {
        "confirm": True,
        "model": model,
        "version": version,
    }
    if model_version is not None:
        body["model_version"] = model_version
    if source_ref is not None:
        body["source_ref"] = source_ref
    if notes is not None:
        body["notes"] = notes
    if session_id is not None:
        body["session_id"] = session_id
    if proposal_signal_id is not None:
        body["proposal_signal_id"] = proposal_signal_id
    return _post(f"/api/agents/{agent_id}/apply-model", body, server_url=server_url)
