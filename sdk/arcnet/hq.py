"""Bounded HQ read helpers for coding / exploration agents (docs/12 agent-view).

Prefer these over dumping full transcripts or raw tool payloads into agent context.
Does not import agents/ or scripts/.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_DEFAULT_BASE = "http://localhost:8000"


def _base(server_url: str | None = None) -> str:
    return (server_url or os.getenv("ARCNET_SERVER_URL") or _DEFAULT_BASE).rstrip("/")


def _get(path: str, *, server_url: str | None = None, timeout: float = 10.0) -> Any:
    url = f"{_base(server_url)}{path}"
    with httpx.Client(timeout=timeout) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def check_session(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Compact session inspection — GET /api/agent-view/check/{session_id}."""
    return _get(f"/api/agent-view/check/{session_id}", server_url=server_url)


def signals_view(
    agent_or_session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Bounded signals envelope — GET /api/agent-view/signals/{id}."""
    return _get(f"/api/agent-view/signals/{agent_or_session_id}", server_url=server_url)


def session_view(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Session context envelope (no full transcript) — GET /api/agent-view/session/{id}."""
    return _get(f"/api/agent-view/session/{session_id}", server_url=server_url)


def incident_view(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Case-file / incident envelope — GET /api/agent-view/incident/{id}."""
    return _get(f"/api/agent-view/incident/{session_id}", server_url=server_url)


def sources_view(
    agent_or_session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Sources envelope for an agent or session — GET /api/agent-view/sources/{id}."""
    return _get(f"/api/agent-view/sources/{agent_or_session_id}", server_url=server_url)
