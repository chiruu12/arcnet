"""Replay loader (Phase 1) — full harness lands in Phase 4 (docs/10)."""

from __future__ import annotations

from typing import Any

import httpx


def load_transcript(
    session_id: str,
    *,
    server_url: str = "http://localhost:8000",
) -> dict[str, Any]:
    """Load a replay-ready transcript from SQLite via the server (SQLite-primary)."""
    base = server_url.rstrip("/")
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{base}/api/sessions/{session_id}", params={"include": "transcript"})
        r.raise_for_status()
        row = r.json()
    transcript = row.get("transcript")
    if isinstance(transcript, str):
        import json

        transcript = json.loads(transcript)
    if not isinstance(transcript, dict):
        raise ValueError(f"session {session_id} has no transcript")
    return transcript


def load_session(
    session_id: str,
    *,
    server_url: str = "http://localhost:8000",
    include_transcript: bool = True,
) -> dict[str, Any]:
    base = server_url.rstrip("/")
    params = {"include": "transcript"} if include_transcript else {}
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{base}/api/sessions/{session_id}", params=params)
        r.raise_for_status()
        return r.json()
