"""Best-effort HITL decide → signals bus + AgentOS relay (docs/02, docs/12)."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

import httpx

from arcnet_server import repository

logger = logging.getLogger("arcnet.hitl_relay")

RELAY_TIMEOUT_S = 2.0
# Same default as replay_service, so the relay is live in the standard bring-up.
# Set ARCNET_AGENTOS_URL="" to record on the signal bus without an HTTP relay.
AGENTOS_DEFAULT_URL = "http://localhost:7777"


def _agentos_base() -> str | None:
    raw = os.getenv("ARCNET_AGENTOS_URL")
    if raw is None:
        raw = AGENTOS_DEFAULT_URL
    base = raw.strip().rstrip("/")
    return base or None


def _resolve_agent_id(conn, session_id: str | None) -> str:
    if not session_id:
        return "unknown"
    session = repository.get_session(conn, session_id)
    if session and session.get("agent_id"):
        return str(session["agent_id"])
    return "unknown"


def _signal_payload(hitl_row: dict[str, Any], decision: str, *, agent_id: str) -> dict[str, Any]:
    hitl_id = str(hitl_row.get("hitl_id") or "")
    session_id = hitl_row.get("session_id")
    if decision == "rejected":
        return {
            "session_id": session_id,
            "agent_id": agent_id,
            "kind": "kill",
            "severity": "critical",
            "reason": f"HITL rejected ({hitl_id})",
            "guidance": "cancel run per operator decision",
            "source": "hitl",
        }
    return {
        "session_id": session_id,
        "agent_id": agent_id,
        "kind": "note",
        "severity": "info",
        "reason": f"HITL approved ({hitl_id})",
        "guidance": (
            "Operator approved — acknowledgement recorded on the signal bus; "
            "no live Agno pause/resume path in ArcNet v1."
        ),
        "source": "hitl",
    }


async def _post_agentos(base: str, payload: dict[str, Any]) -> tuple[bool, str]:
    url = f"{base}/internal/hitl-decide"
    try:
        async with httpx.AsyncClient(timeout=RELAY_TIMEOUT_S) as client:
            res = await client.post(url, json=payload)
        if res.status_code == 200:
            return True, "delivered to AgentOS"
        return False, f"AgentOS HTTP {res.status_code}"
    except httpx.TimeoutException:
        return False, f"AgentOS timeout after {RELAY_TIMEOUT_S:.0f}s"
    except Exception as exc:  # noqa: BLE001 — fail-safe: never raise into request path
        logger.debug("hitl relay http failed: %s", exc)
        return False, f"AgentOS unreachable ({type(exc).__name__})"


async def relay_hitl_decision(
    conn,
    hitl_row: dict[str, Any],
    decision: str,
    *,
    insert_signal: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Relay HITL decide via signals bus + optional AgentOS HTTP (bounded, no retries)."""
    base = _agentos_base()
    agent_id = _resolve_agent_id(conn, hitl_row.get("session_id"))
    signal_body = _signal_payload(hitl_row, decision, agent_id=agent_id)

    relay: dict[str, Any] = {"attempted": False, "delivered": False, "detail": ""}

    # The signal bus is the local control plane: record the decision there whether
    # or not an AgentOS endpoint is configured.
    try:
        insert_signal(signal_body)
    except Exception as exc:  # noqa: BLE001
        relay["detail"] = f"signal bus failed ({type(exc).__name__})"
        return relay

    if not base:
        relay["detail"] = "AgentOS relay disabled; recorded on signal bus"
        return relay

    relay["attempted"] = True

    http_payload = {
        "hitl_id": hitl_row.get("hitl_id"),
        "decision": decision,
        "run_id": hitl_row.get("run_id"),
        "session_id": hitl_row.get("session_id"),
        "agent_id": agent_id,
        "signal_kind": signal_body["kind"],
    }
    delivered, detail = await _post_agentos(base, http_payload)
    relay["delivered"] = delivered
    if delivered:
        relay["detail"] = detail
    else:
        relay["detail"] = f"{detail}; kill/note queued on signal bus"
    return relay
