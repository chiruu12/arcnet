"""Replay-ready transcript recorder (SQLite-primary; docs/10)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from arcnet.context import try_get_runtime
from arcnet.ids import new_id

logger = logging.getLogger("arcnet.transcript")


@dataclass
class TranscriptRecorder:
    session_id: str
    agent_id: str
    goal: str
    model: str
    scenario: str | None = None
    system_prompt_ref: str | None = None
    temperature: float = 0.0
    steps: list[dict[str, Any]] = field(default_factory=list)
    final_output: str | None = None
    outcome: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    status: str = "running"
    started_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    ended_at_ms: int | None = None
    _pending_guard: dict[str, Any] | None = None

    def note_guard(self, **guard: Any) -> None:
        self._pending_guard = {k: v for k, v in guard.items() if v is not None}

    def record_model_turn(self, output: str) -> None:
        digest = hashlib.sha256(output.encode()).hexdigest()[:16]
        self.steps.append({"i": len(self.steps), "type": "model_turn", "output_digest": digest})

    def record_tool_call(
        self,
        *,
        tool: str,
        args: dict[str, Any],
        recorded_output: str | None,
        guard: dict[str, Any] | None = None,
        trust_level: str | None = None,
    ) -> None:
        step: dict[str, Any] = {
            "i": len(self.steps),
            "type": "tool_call",
            "tool": tool,
            "args": args,
            "recorded_output": recorded_output,
        }
        if trust_level:
            step["trust_level"] = trust_level
        g = guard or self._pending_guard
        if g:
            step["guard"] = g
        self._pending_guard = None
        self.steps.append(step)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "scenario": self.scenario,
            "goal": self.goal,
            "system_prompt_ref": self.system_prompt_ref,
            "model": self.model,
            "temperature": self.temperature,
            "steps": self.steps,
            "final_output": self.final_output,
            "outcome": self.outcome,
            "usage": self.usage,
            "trace_id": self.trace_id,
        }

    def finish(
        self,
        *,
        final_output: str | None,
        status: str,
        outcome: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        self.final_output = final_output
        self.status = status
        if outcome:
            self.outcome = outcome
        if usage:
            self.usage = usage
        if trace_id:
            self.trace_id = trace_id
        self.ended_at_ms = int(time.time() * 1000)
        return self.to_dict()


def prompt_ref(path: Path) -> str:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()[:12]
    # Prefer repo-relative path when possible
    try:
        rel = path.resolve().relative_to(Path.cwd().resolve())
        return f"{rel.as_posix()}@{sha}"
    except ValueError:
        return f"{path.name}@{sha}"


def persist_session(
    recorder: TranscriptRecorder,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Upsert session row on arcnet-server (docs/12 write ownership)."""
    rt = try_get_runtime()
    base = (server_url or (rt.server_url if rt else "http://localhost:8000")).rstrip("/")
    body = {
        "session_id": recorder.session_id,
        "agent_id": recorder.agent_id,
        "scenario": recorder.scenario,
        "goal": recorder.goal,
        "system_prompt_ref": recorder.system_prompt_ref,
        "model": recorder.model,
        "temperature": recorder.temperature,
        "status": recorder.status,
        "outcome": recorder.outcome,
        "usage": recorder.usage,
        "trace_id": recorder.trace_id,
        "transcript": recorder.to_dict(),
        "started_at": recorder.started_at_ms,
        "ended_at": recorder.ended_at_ms,
    }
    with httpx.Client(timeout=10.0) as client:
        r = client.post(f"{base}/api/sessions", json=body)
        r.raise_for_status()
        return r.json()


def start_session_row(
    *,
    session_id: str | None = None,
    agent_id: str,
    goal: str,
    model: str,
    scenario: str | None = None,
    system_prompt_ref: str | None = None,
    temperature: float = 0.0,
    server_url: str | None = None,
    exposure: str = "internal",
    agent_name: str | None = None,
    role: str | None = None,
) -> TranscriptRecorder:
    sid = session_id or new_id("s_")
    rec = TranscriptRecorder(
        session_id=sid,
        agent_id=agent_id,
        goal=goal,
        model=model,
        scenario=scenario,
        system_prompt_ref=system_prompt_ref,
        temperature=temperature,
    )
    rt = try_get_runtime()
    base = (server_url or (rt.server_url if rt else "http://localhost:8000")).rstrip("/")
    # Ensure agent row exists
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{base}/api/agents",
                json={
                    "agent_id": agent_id,
                    "name": agent_name or agent_id,
                    "role": role,
                    "exposure": exposure,
                    "model": model,
                },
            )
            client.post(
                f"{base}/api/sessions",
                json={
                    "session_id": sid,
                    "agent_id": agent_id,
                    "scenario": scenario,
                    "goal": goal,
                    "system_prompt_ref": system_prompt_ref,
                    "model": model,
                    "temperature": temperature,
                    "status": "running",
                    "started_at": rec.started_at_ms,
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("session start persist failed: %s", exc)
    return rec
