"""Structured API errors — detail + optional hint for machine consumers (docs/12 additive)."""

from __future__ import annotations

from fastapi import HTTPException


def api_error(status_code: int, detail: str, *, hint: str | None = None) -> HTTPException:
    """Raise HTTPException whose JSON body is ``{detail, hint?}``."""
    body: dict[str, str] = {"detail": detail}
    if hint:
        body["hint"] = hint
    return HTTPException(status_code=status_code, detail=body)


def infer_hint(*, status_code: int, detail: str, path: str) -> str | None:
    """Best-effort next-step hint from status, message, and route."""
    if status_code not in (404, 409):
        return None
    d = detail.lower()
    p = path.lower()
    if "session" in d and "not found" in d:
        return "list ids via GET /api/sessions"
    if "agent" in d and "not found" in d and "session" not in d:
        return "list agents via GET /api/fleet"
    if "replay" in d and "not found" in d:
        return "list replays via GET /api/replays?session_id=<session_id>"
    if "hitl" in d and "not found" in d:
        return "list rows via GET /api/hitl"
    if "proposal" in d and "not found" in d:
        return "list hq_agent proposals via GET /api/signals?source=hq_agent&agent_id=<id>"
    if "no agent or session" in d:
        return "list sessions via GET /api/sessions or agents via GET /api/fleet"
    if "unknown agent-view" in d:
        return (
            "known views: home, fleet_health, signals, time_machine, case_files, "
            "hq_agent, hitl, dashboards, sources_trust, threats, incident, session, "
            "check, fleet, sources, replay — see docs/26-agent-consumer-guide.md"
        )
    if "unknown dashboards scope" in d:
        return "use id=all or id=status"
    if "unknown home scope" in d or (p.endswith("/home/") and "unknown" in d):
        return "use id=all"
    if "version_id" in d and "already exists" in d:
        return "omit version_id to auto-generate or pick a fresh version_id"
    if status_code == 409:
        return "retry with a different id or list existing rows first"
    return None


def normalize_error_body(
    *, status_code: int, detail: object, path: str
) -> dict[str, str]:
    """Normalize any HTTPException detail into ``{detail, hint?}``."""
    if isinstance(detail, dict):
        out = {k: str(v) for k, v in detail.items() if k in ("detail", "hint") and v}
        if "detail" not in out:
            out["detail"] = str(detail)
        if "hint" not in out:
            hint = infer_hint(status_code=status_code, detail=out["detail"], path=path)
            if hint:
                out["hint"] = hint
        return out
    text = str(detail)
    out: dict[str, str] = {"detail": text}
    hint = infer_hint(status_code=status_code, detail=text, path=path)
    if hint:
        out["hint"] = hint
    return out
