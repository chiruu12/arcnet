"""Signal client — SSE subscribe + inline POST /api/signal (stub queue in Phase 1)."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("arcnet.signals")


@dataclass
class Signal:
    session_id: str | None
    agent_id: str
    kind: str  # steer | pause | kill | note
    severity: str  # info | warn | critical
    reason: str
    evidence_link: str | None = None
    guidance: str | None = None
    source: str = "inline"  # inline | alert | griffin | manual


class SignalClient:
    """Phase 1: POST inline signals; in-memory queue for check_signals() (SSE later)."""

    def __init__(self, server_url: str, session_id: str, agent_id: str) -> None:
        self.server_url = server_url.rstrip("/")
        self.session_id = session_id
        self.agent_id = agent_id
        self._queue: deque[dict[str, Any]] = deque()

    def post_signal(
        self,
        *,
        kind: str,
        severity: str,
        reason: str,
        guidance: str | None = None,
        evidence_link: str | None = None,
        source: str = "inline",
    ) -> dict[str, Any] | None:
        payload = {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "kind": kind,
            "severity": severity,
            "reason": reason,
            "guidance": guidance,
            "evidence_link": evidence_link,
            "source": source,
        }
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{self.server_url}/api/signal", json=payload)
                r.raise_for_status()
                row = r.json()
                self._queue.append(row)
                return row
        except Exception as exc:  # noqa: BLE001 — demo: never crash the agent on signal bus
            logger.warning("signal post failed: %s", exc)
            self._queue.append(payload)
            return None

    def check_signals(self) -> list[dict[str, Any]]:
        """Drain pending signals for this session (Phase 1: local queue only)."""
        out: list[dict[str, Any]] = []
        while self._queue:
            out.append(self._queue.popleft())
        return out

    def apply_steer(self, agent: Any, guidance: str) -> None:
        """Primary steer path (G1): write into agent.session_state."""
        if agent is None:
            return
        state = getattr(agent, "session_state", None)
        if state is None:
            agent.session_state = {}
            state = agent.session_state
        state["arcnet_steer"] = guidance
