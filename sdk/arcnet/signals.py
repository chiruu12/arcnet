"""Signal client — SSE subscribe + inline POST /api/signal + steer/kill/pause."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

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
    """POST inline signals; background SSE fills the per-session queue."""

    def __init__(self, server_url: str, session_id: str, agent_id: str) -> None:
        self.server_url = server_url.rstrip("/")
        self.session_id = session_id
        self.agent_id = agent_id
        self._queue: deque[dict[str, Any]] = deque()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_event_id: str | None = None
        self._hitl_pending: dict[str, Any] | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._sse_loop, name="arcnet-sse", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

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
        """Drain pending signals for this session."""
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

    def apply_kill(self, agent: Any) -> bool:
        """Cancel the active Agno run (docs/02)."""
        if agent is None:
            return False
        run_id = getattr(agent, "run_id", None) or getattr(agent, "_run_id", None)
        if run_id and hasattr(agent, "cancel_run"):
            try:
                return bool(agent.cancel_run(str(run_id)))
            except Exception as exc:  # noqa: BLE001
                logger.warning("cancel_run failed: %s", exc)
        # Fallback: mark session_state so middleware can short-circuit
        state = getattr(agent, "session_state", None)
        if state is None:
            agent.session_state = {}
            state = agent.session_state
        state["arcnet_kill"] = True
        return True

    def apply_pause(self, agent: Any, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """HITL pause scaffold — records pending approval; UI decides via /api/hitl."""
        if agent is None:
            return None
        state = getattr(agent, "session_state", None)
        if state is None:
            agent.session_state = {}
            state = agent.session_state
        state["arcnet_pause"] = True
        hitl = {
            "run_id": str(getattr(agent, "run_id", None) or self.session_id),
            "session_id": self.session_id,
            "payload": payload or {"reason": "manual pause"},
        }
        self._hitl_pending = hitl
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{self.server_url}/api/hitl", json=hitl)
                r.raise_for_status()
                return r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("hitl create failed: %s", exc)
            return hitl

    def apply_signals(self, agent: Any, signals: list[dict[str, Any]] | None = None) -> list[str]:
        """Apply a batch of signals to the agent; return kinds acted on."""
        acted: list[str] = []
        for sig in signals if signals is not None else self.check_signals():
            kind = sig.get("kind")
            if kind == "steer" and sig.get("guidance"):
                self.apply_steer(agent, sig["guidance"])
                acted.append("steer")
            elif kind == "kill":
                self.apply_kill(agent)
                acted.append("kill")
            elif kind == "pause":
                self.apply_pause(agent, {"reason": sig.get("reason"), "guidance": sig.get("guidance")})
                acted.append("pause")
            elif kind == "note":
                acted.append("note")
        return acted

    def _sse_loop(self) -> None:
        """Background SSE reader — reconnects with Last-Event-ID (docs/12)."""
        while not self._stop.is_set():
            try:
                qs = urlencode({"session_id": self.session_id})
                url = f"{self.server_url}/signals/stream?{qs}"
                headers: dict[str, str] = {"Accept": "text/event-stream"}
                if self._last_event_id:
                    headers["Last-Event-ID"] = self._last_event_id
                with httpx.Client(timeout=None) as client:
                    with client.stream("GET", url, headers=headers) as resp:
                        if resp.status_code >= 400:
                            logger.warning("sse http %s", resp.status_code)
                            time.sleep(2.0)
                            continue
                        event_name = "message"
                        event_id: str | None = None
                        data_lines: list[str] = []
                        for line in resp.iter_lines():
                            if self._stop.is_set():
                                return
                            if line == "":
                                if data_lines:
                                    raw = "\n".join(data_lines)
                                    self._handle_sse(event_name, event_id, raw)
                                event_name = "message"
                                event_id = None
                                data_lines = []
                                continue
                            if line.startswith(":"):
                                continue
                            if line.startswith("event:"):
                                event_name = line[6:].strip()
                            elif line.startswith("id:"):
                                event_id = line[3:].strip()
                            elif line.startswith("data:"):
                                data_lines.append(line[5:].lstrip())
            except Exception as exc:  # noqa: BLE001
                if not self._stop.is_set():
                    logger.debug("sse reconnect: %s", exc)
                    time.sleep(1.5)

    def _handle_sse(self, event: str, event_id: str | None, raw: str) -> None:
        if event_id:
            self._last_event_id = event_id
        if event not in ("signal", "threat", "hitl_request", "replay_progress"):
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if event == "signal":
            # Dedup: skip if we already queued this signal_id from inline POST
            sid = data.get("signal_id")
            if sid and any(q.get("signal_id") == sid for q in self._queue):
                return
            self._queue.append(data)
        elif event == "hitl_request":
            self._hitl_pending = data
