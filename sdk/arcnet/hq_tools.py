"""HQ Agent callable tools — HTTP/SDK client over ArcNet APIs (docs/18).

Bounded envelopes only. Does not import agents/ or scripts/.
Griffin anomalies are labeled MAD (TabFM not live; TabPFN optional later).

Error contract (Wave B): tools return structured ``{ok:false, error, tool, …}``
for catalog/network/timeout blips — never raise into the Agno loop for those.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from arcnet.hq import check_session, incident_view, signals_view
from arcnet.model_explore import compare_replay_verdicts as _compare_replay_verdicts
from arcnet.model_explore import recommend_models as _recommend_models

_DEFAULT_BASE = "http://localhost:8000"
_GET_RETRIES = 2
_RETRY_BACKOFF_S = 0.15


def _base(server_url: str | None = None) -> str:
    return (server_url or os.getenv("ARCNET_SERVER_URL") or _DEFAULT_BASE).rstrip("/")


def _tool_error(tool: str, error: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "error": error, "tool": tool}
    out.update(extra)
    return out


def _is_error_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and (
        payload.get("ok") is False or "error" in payload
    )


def _get(
    path: str,
    *,
    server_url: str | None = None,
    timeout: float = 10.0,
    tool: str = "http_get",
    retries: int = _GET_RETRIES,
) -> Any:
    """Idempotent GET with bounded retries. Returns JSON or structured error dict."""
    url = f"{_base(server_url)}{path}"
    last: dict[str, Any] | None = None
    attempts = max(1, retries + 1)
    for i in range(attempts):
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(url)
                r.raise_for_status()
                return r.json()
        except httpx.TimeoutException:
            last = _tool_error(tool, "timeout", path=path, timeout_s=timeout)
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = exc.response.text[:300]
            except Exception:  # noqa: BLE001
                detail = str(exc)
            # Non-retryable HTTP errors
            return _tool_error(
                tool,
                "http_error",
                path=path,
                status=exc.response.status_code,
                detail=detail,
            )
        except httpx.HTTPError as exc:
            last = _tool_error(
                tool, "transport_error", path=path, detail=str(exc)[:300]
            )
        if i + 1 < attempts:
            time.sleep(_RETRY_BACKOFF_S * (i + 1))
    return last or _tool_error(tool, "transport_error", path=path)


def _post(
    path: str,
    body: dict[str, Any],
    *,
    server_url: str | None = None,
    timeout: float = 10.0,
    tool: str = "http_post",
) -> Any:
    """POST once (not retried). Returns JSON or structured error dict."""
    url = f"{_base(server_url)}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        return _tool_error(tool, "timeout", path=path, timeout_s=timeout)
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.text[:300]
        except Exception:  # noqa: BLE001
            detail = str(exc)
        return _tool_error(
            tool,
            "http_error",
            path=path,
            status=exc.response.status_code,
            detail=detail,
        )
    except httpx.HTTPError as exc:
        return _tool_error(
            tool, "transport_error", path=path, detail=str(exc)[:300]
        )


def _wrap_ok(tool: str, payload: Any) -> Any:
    if _is_error_payload(payload):
        if isinstance(payload, dict) and payload.get("tool") is None:
            return {**payload, "ok": False, "tool": tool}
        if isinstance(payload, dict) and "ok" not in payload:
            return {**payload, "ok": False, "tool": tool}
        return payload
    if isinstance(payload, dict):
        return {**payload, "ok": True, "tool": tool}
    return {"ok": True, "tool": tool, "data": payload}


def signoz_status(*, server_url: str | None = None) -> dict[str, Any]:
    """What SigNoz is tracking from ArcNet's probe — status + dashboard UUIDs."""
    return _wrap_ok(
        "signoz_status",
        _get("/api/signoz/status", server_url=server_url, tool="signoz_status", timeout=8.0),
    )


def signoz_evidence(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Bounded SigNoz Query Range / trace summary for a session (no full payloads)."""
    sid = (session_id or "").strip()
    if not sid:
        return _tool_error("signoz_evidence", "session_id required")
    return _wrap_ok(
        "signoz_evidence",
        _get(
            f"/api/signoz/evidence?session_id={sid}",
            server_url=server_url,
            tool="signoz_evidence",
            timeout=12.0,
        ),
    )


def fleet_overview(*, server_url: str | None = None) -> Any:
    out = _get("/api/fleet", server_url=server_url, tool="fleet_overview")
    if _is_error_payload(out):
        return _wrap_ok("fleet_overview", out)
    return out


def agent_signals(
    agent_or_session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    try:
        out = signals_view(agent_or_session_id, server_url=server_url)
    except Exception as exc:  # noqa: BLE001
        return _tool_error(
            "agent_signals",
            "signals_failed",
            detail=str(exc)[:300],
            id=agent_or_session_id,
        )
    return _wrap_ok("agent_signals", out)


def session_check(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Compact check envelope — prefer version_pinpoint.narrative for change attribution."""
    try:
        out = check_session(session_id, server_url=server_url)
    except Exception as exc:  # noqa: BLE001
        return _tool_error(
            "session_check",
            "check_failed",
            session_id=session_id,
            detail=str(exc)[:300],
        )
    if isinstance(out, dict):
        data = out.get("data") if isinstance(out.get("data"), dict) else out
        pin = (data or {}).get("version_pinpoint") if isinstance(data, dict) else None
        if isinstance(pin, dict) and pin.get("narrative"):
            out = dict(out)
            out["pinpoint_hint"] = pin["narrative"]
            related = (data or {}).get("related_views") if isinstance(data, dict) else None
            if isinstance(related, dict):
                out["evidence_pointers"] = {k: v for k, v in related.items() if v}
    return _wrap_ok("session_check", out)


def case_file_view(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Bounded Case File / incident envelope (no zip, no full tool dumps)."""
    try:
        out = incident_view(session_id, server_url=server_url)
    except Exception as exc:  # noqa: BLE001
        return _tool_error(
            "case_file_view",
            "incident_failed",
            session_id=session_id,
            detail=str(exc)[:300],
        )
    return _wrap_ok("case_file_view", out)


def replay_compare(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Bounded Time Machine verdict summaries for a session."""
    try:
        out = _compare_replay_verdicts(session_id, server_url=server_url)
    except Exception as exc:  # noqa: BLE001
        return _tool_error(
            "replay_compare",
            "compare_failed",
            session_id=session_id,
            detail=str(exc)[:300],
        )
    return _wrap_ok("replay_compare", out)


def griffin_anomalies(*, server_url: str | None = None) -> dict[str, Any]:
    """Griffin cache + recent griffin-sourced signals. Estimator = MAD (honest)."""
    status = _get("/api/griffin/status", server_url=server_url, tool="griffin_anomalies")
    if _is_error_payload(status):
        return _wrap_ok("griffin_anomalies", status)
    signals = _get(
        "/api/signals?source=griffin&limit=20&offset=0",
        server_url=server_url,
        tool="griffin_anomalies",
    )
    griffin_sigs = [
        s for s in (signals if isinstance(signals, list) else []) if isinstance(s, dict)
    ]
    return {
        "ok": True,
        "tool": "griffin_anomalies",
        "estimator": "mad",
        "note": (
            "Griffin uses MAD (median/MAD robust z-score). "
            "TabFM too slow; TabPFN needs TABPFN_TOKEN."
        ),
        "status": status,
        "recent_griffin_signals": griffin_sigs[:20],
    }


def list_agent_models(
    agent_id: str,
    *,
    server_url: str | None = None,
) -> Any:
    out = _get(
        f"/api/agents/{agent_id}/models",
        server_url=server_url,
        tool="list_agent_models",
    )
    if _is_error_payload(out):
        return _wrap_ok("list_agent_models", out)
    return out


def recommend_models(
    task_type: str,
    *,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Exploration-only ranking. Live OpenAI list when OPENAI_API_KEY set (or constraints.live)."""
    try:
        out = _recommend_models(task_type, constraints=constraints)
    except Exception as exc:  # noqa: BLE001 — never raise for catalog blips
        return _tool_error(
            "recommend_models",
            "recommend_failed",
            detail=str(exc)[:300],
            task_type=task_type,
        )
    return _wrap_ok("recommend_models", out)


def agent_version_timeline(
    agent_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    return _wrap_ok(
        "agent_version_timeline",
        _get(
            f"/api/agents/{agent_id}/versions/timeline",
            server_url=server_url,
            tool="agent_version_timeline",
        ),
    )


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
    return _wrap_ok(
        "register_agent_version",
        _post(
            f"/api/agents/{agent_id}/versions",
            body,
            server_url=server_url,
            tool="register_agent_version",
        ),
    )


def _collect_evidence_refs(
    *,
    agent_id: str,
    session_id: str | None,
    task_type: str | None,
    server_url: str | None,
) -> list[str]:
    """Bounded evidence pointers for propose_model_change (strings only)."""
    refs: list[str] = [f"agent:{agent_id}"]
    if task_type:
        refs.append(f"task_type:{task_type}")
    if session_id:
        refs.append(f"session:{session_id}")
        check = _get(
            f"/api/agent-view/check/{session_id}",
            server_url=server_url,
            tool="propose_model_change",
            timeout=8.0,
        )
        if isinstance(check, dict) and not _is_error_payload(check):
            data = check.get("data") if isinstance(check.get("data"), dict) else {}
            pin = (data or {}).get("version_pinpoint") if isinstance(data, dict) else None
            if isinstance(pin, dict) and pin.get("version_id"):
                refs.append(f"version_id:{pin['version_id']}")
            links = check.get("links") if isinstance(check.get("links"), dict) else {}
            if isinstance(links, dict) and links.get("signoz_trace"):
                refs.append("signoz_trace:present")
        replays = _get(
            f"/api/replays?session_id={session_id}&limit=5",
            server_url=server_url,
            tool="propose_model_change",
            timeout=8.0,
        )
        if isinstance(replays, list):
            for row in replays[:5]:
                if isinstance(row, dict) and row.get("replay_id"):
                    refs.append(f"replay:{row['replay_id']}")
    griffin = _get(
        "/api/griffin/status",
        server_url=server_url,
        tool="propose_model_change",
        timeout=5.0,
    )
    if isinstance(griffin, dict) and not _is_error_payload(griffin):
        anomalies = griffin.get("anomalies") or griffin.get("last_anomaly")
        if isinstance(anomalies, list) and anomalies:
            first = anomalies[0]
            if isinstance(first, dict):
                sid = first.get("series_id") or first.get("fingerprint")
                if sid:
                    refs.append(f"griffin:{sid}")
        elif isinstance(anomalies, dict) and anomalies.get("series_id"):
            refs.append(f"griffin:{anomalies['series_id']}")
        est = griffin.get("estimator") or griffin.get("model")
        if est:
            refs.append(f"griffin_estimator:{est}")
    signoz = _get(
        "/api/signoz/status",
        server_url=server_url,
        tool="propose_model_change",
        timeout=5.0,
    )
    if isinstance(signoz, dict) and not _is_error_payload(signoz):
        dash = signoz.get("dashboards") if isinstance(signoz.get("dashboards"), dict) else {}
        if isinstance(dash, dict):
            for slot, uuid in dash.items():
                if uuid:
                    refs.append(f"signoz_dashboard:{slot}:{uuid}")
                    break  # one UUID is enough for bounded evidence
    # Dedupe + hard cap
    seen: set[str] = set()
    out: list[str] = []
    for r in refs:
        s = str(r)[:160]
        if s not in seen:
            seen.add(s)
            out.append(s)
        if len(out) >= 12:
            break
    return out


def propose_model_change(
    agent_id: str,
    to_model: str,
    reason: str,
    *,
    from_model: str | None = None,
    task_type: str | None = None,
    session_id: str | None = None,
    evidence_refs: list[str] | None = None,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Record a proposal note — does not mutate live agent config.

    Attaches bounded ``evidence_refs`` (check / replay / griffin / signoz ids).
    """
    refs = list(evidence_refs or [])
    if not refs:
        refs = _collect_evidence_refs(
            agent_id=agent_id,
            session_id=session_id,
            task_type=task_type,
            server_url=server_url,
        )
    else:
        refs = [str(r)[:160] for r in refs[:12]]
    from_bit = f"{from_model} → " if from_model else ""
    guidance = (
        f"Proposed model change for {agent_id}: {from_bit}{to_model}."
        + (f" task_type={task_type}." if task_type else "")
        + " Apply via POST /api/agents/{id}/apply-model with confirm:true (human-gated)."
        + (f" evidence_refs={','.join(refs[:6])}." if refs else "")
    )
    body: dict[str, Any] = {
        "agent_id": agent_id,
        "kind": "note",
        "severity": "info",
        "reason": reason[:500],
        "guidance": guidance[:800],
        "source": "hq_agent",
    }
    if session_id:
        body["session_id"] = session_id
    out = _post("/api/signal", body, server_url=server_url, tool="propose_model_change")
    if _is_error_payload(out):
        return _wrap_ok("propose_model_change", out)
    if isinstance(out, dict):
        out = {**out, "evidence_refs": refs, "ok": True, "tool": "propose_model_change"}
        return out
    return {
        "ok": True,
        "tool": "propose_model_change",
        "data": out,
        "evidence_refs": refs,
    }


def list_model_proposals(
    *,
    agent_id: str | None = None,
    server_url: str | None = None,
    limit: int = 30,
) -> Any:
    # Filter at the API so newer non-hq_agent signals cannot hide proposals.
    q = f"/api/signals?source=hq_agent&limit={limit}&offset=0"
    if agent_id:
        q += f"&agent_id={agent_id}"
    rows = _get(q, server_url=server_url, tool="list_model_proposals")
    if _is_error_payload(rows):
        return _wrap_ok("list_model_proposals", rows)
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
    """Human-gated apply — requires confirm=True; records version bump on the server.

    SQLite apply does **not** restart AgentOS. Response always includes
    ``agentos_reload_required: true`` when applied.
    """
    if confirm is not True:
        return {
            "ok": False,
            "tool": "apply_model_change",
            "applied": False,
            "error": "confirm=True required (human-gated; refusing silent apply)",
            "agentos_reload_required": False,
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
    out = _post(
        f"/api/agents/{agent_id}/apply-model",
        body,
        server_url=server_url,
        tool="apply_model_change",
    )
    if _is_error_payload(out):
        return _wrap_ok("apply_model_change", out)
    if isinstance(out, dict):
        out = dict(out)
        out.setdefault("agentos_reload_required", True)
        out.setdefault(
            "agentos_reload_instructions",
            (
                "SQLite model/version updated; live AgentOS process still uses the old "
                "model until restarted. Do not auto-mutate AgentOS config from the server."
            ),
        )
        out["ok"] = True
        out["tool"] = "apply_model_change"
        # Best-effort health probe (never auto-restart)
        aos = (os.getenv("ARCNET_AGENTOS_URL") or "").strip()
        if aos:
            try:
                with httpx.Client(timeout=3.0) as client:
                    r = client.get(aos.rstrip("/") + "/health")
                    out["agentos_health"] = {
                        "url": aos,
                        "status": r.status_code,
                        "note": "probe only — restart AgentOS manually if model mismatch",
                    }
            except Exception as exc:  # noqa: BLE001
                out["agentos_health"] = {
                    "url": aos,
                    "error": str(exc)[:200],
                    "note": "AgentOS unreachable; reload still required after apply",
                }
        return out
    return _wrap_ok("apply_model_change", out)
