"""Input validation + size bounds for hostile request hardening (docs/30)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request

# Adversarial caps — storage + echo guardrails (docs/30).
MAX_TRANSCRIPT_BYTES = 1_048_576
MAX_TEXT_CHARS = 16_384
MAX_HITL_PAYLOAD_BYTES = 65_536


async def parse_json_object(request: Request) -> dict[str, Any]:
    """Parse body as JSON object; 400 on empty, malformed, or non-object."""
    try:
        raw = await request.body()
    except Exception as exc:  # noqa: BLE001 — never 500 on read
        raise HTTPException(400, "request body must be JSON") from exc
    if not raw or not raw.strip():
        raise HTTPException(400, "request body must be JSON")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "request body must be JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")
    return body


def require_fields(body: dict[str, Any], *names: str) -> None:
    """400 when any named field is missing or blank."""
    missing = [
        n
        for n in names
        if body.get(n) is None or (isinstance(body.get(n), str) and not body[n].strip())
    ]
    if missing:
        raise HTTPException(400, f"missing required field(s): {', '.join(missing)}")


def _clip_str(val: Any, limit: int, field: str) -> str | None:
    if val is None:
        return None
    s = str(val)
    if len(s) > limit:
        raise HTTPException(422, f"{field} exceeds {limit} characters")
    return s


def _bound_json_size(obj: Any, limit: int, field: str) -> None:
    try:
        nbytes = len(json.dumps(obj, separators=(",", ":"), default=str).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"{field} must be JSON-serializable") from exc
    if nbytes > limit:
        raise HTTPException(422, f"{field} exceeds {limit} bytes")


def bound_session_body(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    if out.get("goal") is not None:
        out["goal"] = _clip_str(out["goal"], MAX_TEXT_CHARS, "goal")
    if out.get("transcript") is not None:
        _bound_json_size(out["transcript"], MAX_TRANSCRIPT_BYTES, "transcript")
    return out


def bound_signal_body(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    for key in ("reason", "guidance", "evidence_link"):
        if out.get(key) is not None:
            out[key] = _clip_str(out[key], MAX_TEXT_CHARS, key)
    return out


def bound_threat_body(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    if out.get("evidence") is not None:
        out["evidence"] = _clip_str(out["evidence"], MAX_TEXT_CHARS, "evidence")
    return out


def bound_hitl_body(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    if out.get("payload") is not None:
        _bound_json_size(out["payload"], MAX_HITL_PAYLOAD_BYTES, "payload")
    return out


def bound_source_body(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    detail = out.get("findings_detail")
    if detail is not None:
        _bound_json_size(detail, MAX_HITL_PAYLOAD_BYTES, "findings_detail")
    return out
