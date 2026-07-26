"""ArcNet MCP server — read tools over local HTTP API (docs/12 agent-view twins).

HTTP GETs use the JSON default (`format=json`). Tool results are returned as
pretty-printed JSON text for structured MCP consumption. Agents that want the
token-efficient TOON twin should call the same paths with `?format=toon`
directly (Content-Type: text/toon) — this package does not request TOON.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

DEFAULT_BASE = "http://localhost:8000"


def base_url() -> str:
    return (os.getenv("ARCNET_SERVER_URL") or DEFAULT_BASE).rstrip("/")


def _get(path: str, *, params: dict[str, Any] | None = None) -> Any:
    """GET JSON from ArcNet (default format). Does not pass format=toon."""
    with httpx.Client(timeout=20.0) as client:
        r = client.get(f"{base_url()}{path}", params=params)
        r.raise_for_status()
        return r.json()


def _post(path: str, body: dict[str, Any]) -> Any:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{base_url()}{path}", json=body)
        r.raise_for_status()
        return r.json()


def fleet_health() -> dict[str, Any]:
    return _get("/api/agent-view/fleet_health/all")


def search_threats(
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if agent_id:
        params["agent_id"] = agent_id
    if session_id:
        params["session_id"] = session_id
    return _get("/api/agent-view/threats", params=params)


def get_incident(session_id: str) -> dict[str, Any]:
    return _get(f"/api/agent-view/incident/{session_id}")


def case_file(session_id: str) -> dict[str, Any]:
    return _get(f"/api/agent-view/case_files/{session_id}")


def replay_verdicts(session_id: str) -> dict[str, Any]:
    return _get(f"/api/agent-view/time_machine/{session_id}")


def model_intel(agent_id: str) -> dict[str, Any]:
    return _get(f"/api/agents/{agent_id}/model-intel")


def search_models(
    *,
    provider: str | None = None,
    status: str | None = None,
    capability_tier: str | None = None,
    min_context: int | None = None,
    reasoning: bool | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if provider:
        params["provider"] = provider
    if status:
        params["status"] = status
    if capability_tier:
        params["capability_tier"] = capability_tier
    if min_context is not None:
        params["min_context"] = min_context
    if reasoning is not None:
        params["reasoning"] = reasoning
    return _get("/api/models/catalog", params=params or None)


def signals(
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if agent_id:
        params["agent_id"] = agent_id
    if session_id:
        params["session_id"] = session_id
    return _get("/api/agent-view/signals", params=params)


def run_replay(*, session_id: str, candidate_model: str, confirm: bool) -> dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "error": "confirm_required",
            "detail": "Set confirm=true to execute a live replay",
        }
    return _post(
        "/api/replay",
        {"session_id": session_id, "candidate_model": candidate_model},
    )


def propose_model_change(
    *,
    agent_id: str,
    to_model: str,
    reason: str,
    confirm: bool,
    from_model: str | None = None,
) -> dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "error": "confirm_required",
            "detail": "Set confirm=true to record a proposal signal",
        }
    body: dict[str, Any] = {
        "agent_id": agent_id,
        "kind": "note",
        "severity": "info",
        "reason": reason[:500],
        "guidance": (
            f"Proposed model change for {agent_id}: "
            f"{from_model + ' → ' if from_model else ''}{to_model}. "
            f"Apply via POST /api/agents/{agent_id}/apply-model with confirm:true."
        )[:800],
        "source": "arcnet_mcp",
    }
    return _post("/api/signal", body)


def as_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)[:120_000]
