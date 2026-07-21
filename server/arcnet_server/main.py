"""ArcNet server — SQLite + signal bus + Griffin + Phase 3 routes (docs/12)."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from arcnet_server.bus import BUS
from arcnet_server.db import connect, dumps, init_db, now_ms, row_to_dict

_conn = None
_griffin_task: asyncio.Task | None = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = connect()
        init_db(_conn)
    return _conn


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _griffin_task
    get_conn()
    # Griffin worker (MAD) — demo cadence when ARCNET_GRIFFIN_DEMO=1
    try:
        from arcnet_server.griffin import griffin_loop

        cadence = float(os.getenv("ARCNET_GRIFFIN_CADENCE_S", "60"))
        if os.getenv("ARCNET_GRIFFIN_DEMO", "").strip() in ("1", "true", "yes"):
            cadence = float(os.getenv("ARCNET_GRIFFIN_DEMO_CADENCE_S", "10"))
        _griffin_task = asyncio.create_task(griffin_loop(get_conn, cadence_s=cadence))
    except Exception:  # noqa: BLE001
        _griffin_task = None
    yield
    if _griffin_task is not None:
        _griffin_task.cancel()
        try:
            await _griffin_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="arcnet-server", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _new_id(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(4)}"


def _insert_signal(body: dict[str, Any], *, status: str = "pending") -> dict[str, Any]:
    signal_id = body.get("signal_id") or _new_id("sig_")
    ts = now_ms()
    conn = get_conn()
    conn.execute(
        """INSERT INTO signals
           (signal_id, session_id, agent_id, kind, severity, reason, evidence_link, guidance, source, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            signal_id,
            body.get("session_id"),
            body["agent_id"],
            body["kind"],
            body["severity"],
            body["reason"],
            body.get("evidence_link"),
            body.get("guidance"),
            body.get("source") or "inline",
            status,
            ts,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM signals WHERE signal_id=?", (signal_id,)).fetchone()
    d = row_to_dict(row)
    assert d is not None
    BUS.publish("signal", d)
    return d


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agents")
async def upsert_agent(request: Request) -> dict[str, Any]:
    body = await request.json()
    agent_id = body["agent_id"]
    name = body.get("name") or agent_id
    role = body.get("role")
    exposure = body.get("exposure") or "internal"
    model = body.get("model")
    ts = now_ms()
    conn = get_conn()
    existing = conn.execute("SELECT agent_id FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE agents SET name=?, role=?, exposure=?, model=?, last_seen=? WHERE agent_id=?",
            (name, role, exposure, model, ts, agent_id),
        )
    else:
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
            (agent_id, name, role, exposure, model, ts, ts),
        )
    conn.commit()
    row = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    return row_to_dict(row)  # type: ignore[return-value]


@app.post("/api/sessions")
async def upsert_session(request: Request) -> dict[str, Any]:
    body = await request.json()
    session_id = body.get("session_id") or _new_id("s_")
    agent_id = body["agent_id"]
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM agents WHERE agent_id=?", (agent_id,)).fetchone():
        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, exposure, model, first_seen, last_seen) VALUES (?,?,?,?,?,?)",
            (agent_id, agent_id, body.get("exposure") or "internal", body.get("model"), ts, ts),
        )
    fields = {
        "session_id": session_id,
        "agent_id": agent_id,
        "scenario": body.get("scenario"),
        "goal": body.get("goal"),
        "system_prompt_ref": body.get("system_prompt_ref"),
        "model": body.get("model"),
        "temperature": body.get("temperature"),
        "status": body.get("status") or "running",
        "outcome": dumps(body.get("outcome")),
        "usage": dumps(body.get("usage")),
        "trace_id": body.get("trace_id"),
        "transcript": dumps(body.get("transcript")),
        "started_at": body.get("started_at") or now_ms(),
        "ended_at": body.get("ended_at"),
    }
    existing = conn.execute("SELECT session_id FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if existing:
        conn.execute(
            """UPDATE sessions SET agent_id=?, scenario=?, goal=?, system_prompt_ref=?, model=?,
               temperature=?, status=?, outcome=?, usage=?, trace_id=?,
               transcript=COALESCE(?, transcript), started_at=COALESCE(?, started_at), ended_at=?
               WHERE session_id=?""",
            (
                fields["agent_id"],
                fields["scenario"],
                fields["goal"],
                fields["system_prompt_ref"],
                fields["model"],
                fields["temperature"],
                fields["status"],
                fields["outcome"],
                fields["usage"],
                fields["trace_id"],
                fields["transcript"],
                fields["started_at"],
                fields["ended_at"],
                session_id,
            ),
        )
    else:
        conn.execute(
            """INSERT INTO sessions
               (session_id, agent_id, scenario, goal, system_prompt_ref, model, temperature,
                status, outcome, usage, trace_id, transcript, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fields["session_id"],
                fields["agent_id"],
                fields["scenario"],
                fields["goal"],
                fields["system_prompt_ref"],
                fields["model"],
                fields["temperature"],
                fields["status"],
                fields["outcome"],
                fields["usage"],
                fields["trace_id"],
                fields["transcript"],
                fields["started_at"],
                fields["ended_at"],
            ),
        )
    conn.commit()
    return get_session(session_id, include="transcript")


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, include: str | None = Query(default=None)) -> dict[str, Any]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"session {session_id} not found")
    d = row_to_dict(row, json_fields=["outcome", "usage", "transcript"])
    assert d is not None
    if include != "transcript":
        d.pop("transcript", None)
    return d


@app.post("/api/signal")
async def post_signal(request: Request) -> dict[str, Any]:
    body = await request.json()
    return _insert_signal(body)


@app.get("/signals/stream")
async def signals_stream(
    request: Request,
    session_id: str | None = None,
) -> EventSourceResponse:
    """SSE firehose / per-session stream with Last-Event-ID replay (docs/12)."""

    async def gen():
        # Replay missed rows from tables when Last-Event-ID present
        last = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
        conn = get_conn()
        if last and last.isdigit():
            # Best-effort: replay recent pending signals (event ids are bus seq, not signal_ids).
            # On reconnect, dump last 50 matching rows as catch-up.
            q = "SELECT * FROM signals WHERE 1=1"
            params: list[Any] = []
            if session_id:
                # Same scoping as the live filter below: session rows plus
                # agent-wide rows (session_id NULL, e.g. Griffin) are delivered.
                q += " AND (session_id = ? OR session_id IS NULL)"
                params.append(session_id)
            q += " ORDER BY created_at DESC LIMIT 50"
            rows = list(reversed(conn.execute(q, params).fetchall()))
            for row in rows:
                d = row_to_dict(row)
                if d:
                    yield {"event": "signal", "id": d["signal_id"], "data": json.dumps(d)}

        q = BUS.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                if session_id and ev.event == "signal":
                    sid = (ev.data or {}).get("session_id")
                    if sid and sid != session_id:
                        continue
                yield {
                    "event": ev.event,
                    "id": ev.event_id,
                    "data": json.dumps(ev.data),
                }
        finally:
            BUS.unsubscribe(q)

    return EventSourceResponse(gen())


@app.post("/api/threats")
async def post_threat(request: Request) -> dict[str, Any]:
    body = await request.json()
    threat_id = body.get("threat_id") or _new_id("thr_")
    ts = now_ms()
    conn = get_conn()
    conn.execute(
        """INSERT INTO threats
           (threat_id, session_id, agent_id, checkpoint, action, category, subcategory,
            risk_score, trust_level, evidence, trace_id, span_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            threat_id,
            body.get("session_id"),
            body.get("agent_id"),
            body.get("checkpoint"),
            body.get("action"),
            body.get("category"),
            body.get("subcategory"),
            body.get("risk_score"),
            body.get("trust_level"),
            body.get("evidence"),
            body.get("trace_id"),
            body.get("span_id"),
            ts,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM threats WHERE threat_id=?", (threat_id,)).fetchone()
    d = row_to_dict(row)
    assert d is not None
    BUS.publish("threat", d)
    return d


@app.get("/api/threats")
def list_threats(
    since: int | None = None,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    conn = get_conn()
    q = "SELECT * FROM threats WHERE 1=1"
    params: list[Any] = []
    if since is not None:
        q += " AND created_at >= ?"
        params.append(since)
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    q += " ORDER BY created_at DESC LIMIT 200"
    rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


@app.post("/api/sources")
async def post_source(request: Request) -> dict[str, Any]:
    body = await request.json()
    source_id = body.get("source_id") or _new_id("src_")
    ts = now_ms()
    conn = get_conn()
    conn.execute(
        """INSERT INTO sources
           (source_id, session_id, agent_id, origin, trust_level, scan_action, findings, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            source_id,
            body.get("session_id"),
            body.get("agent_id"),
            body.get("origin"),
            body.get("trust_level"),
            body.get("scan_action"),
            body.get("findings") or 0,
            ts,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
    return row_to_dict(row)  # type: ignore[return-value]


@app.get("/api/sources")
def list_sources(
    agent_id: str | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    conn = get_conn()
    q = "SELECT * FROM sources WHERE 1=1"
    params: list[Any] = []
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    if session_id:
        q += " AND session_id = ?"
        params.append(session_id)
    q += " ORDER BY created_at DESC LIMIT 200"
    rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


@app.post("/api/hitl")
async def create_hitl(request: Request) -> dict[str, Any]:
    """Create a HITL approval row (pause scaffold)."""
    body = await request.json()
    hitl_id = body.get("hitl_id") or _new_id("hitl_")
    ts = now_ms()
    conn = get_conn()
    conn.execute(
        """INSERT INTO hitl_requests (hitl_id, run_id, session_id, payload, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            hitl_id,
            body["run_id"],
            body.get("session_id"),
            dumps(body.get("payload")),
            "pending",
            ts,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM hitl_requests WHERE hitl_id=?", (hitl_id,)).fetchone()
    d = row_to_dict(row, json_fields=["payload"])
    assert d is not None
    BUS.publish("hitl_request", d)
    return d


@app.post("/api/hitl/{hitl_id}")
async def decide_hitl(hitl_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    decision = body.get("decision")
    if decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be approved|rejected")
    conn = get_conn()
    row = conn.execute("SELECT * FROM hitl_requests WHERE hitl_id=?", (hitl_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"hitl {hitl_id} not found")
    ts = now_ms()
    conn.execute(
        "UPDATE hitl_requests SET status=?, decided_at=? WHERE hitl_id=?",
        (decision, ts, hitl_id),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM hitl_requests WHERE hitl_id=?", (hitl_id,)).fetchone()
    return row_to_dict(updated, json_fields=["payload"])  # type: ignore[return-value]


def _kind_from_labels(labels: dict[str, Any]) -> tuple[str, str]:
    """Map alert labels → (signal kind, severity)."""
    arcnet_kind = str(labels.get("arcnet_kind") or labels.get("severity") or "note").lower()
    mapping = {
        "threat": ("steer", "critical"),
        "kill": ("kill", "critical"),
        "cost_burn": ("kill", "critical"),
        "griffin": ("note", "warn"),
        "steer": ("steer", "critical"),
        "pause": ("pause", "warn"),
        "note": ("note", "info"),
        "seasonal": ("note", "info"),
    }
    return mapping.get(arcnet_kind, ("note", "warn"))


@app.post("/webhooks/signoz")
async def signoz_webhook(request: Request):
    """SigNoz alert webhook — dedupe + map labels → Signal (docs/12)."""
    body = await request.json()
    conn = get_conn()
    ts = now_ms()
    alerts = body.get("alerts") or [body]
    overall = str(body.get("status") or "").lower()
    window_ms = 5 * 60 * 1000

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        labels = dict(alert.get("labels") or {})
        fingerprint = str(alert.get("fingerprint") or labels.get("alertname") or "unknown")
        status = str(alert.get("status") or overall or "firing").lower()

        earlier = conn.execute(
            """SELECT 1 FROM webhook_events
               WHERE fingerprint=? AND received_at >= ?
               LIMIT 1""",
            (fingerprint, ts - window_ms),
        ).fetchone()

        conn.execute(
            "INSERT INTO webhook_events (fingerprint, status, payload, received_at) VALUES (?,?,?,?)",
            (fingerprint, status, dumps(alert), ts),
        )

        if status in ("resolved", "ok"):
            agent_id = labels.get("agent_id") or labels.get("arcnet.agent_id")
            if agent_id:
                conn.execute(
                    """UPDATE signals SET status='expired'
                       WHERE agent_id=? AND source='alert' AND status IN ('pending','delivered')
                       AND created_at >= ?""",
                    (agent_id, ts - window_ms),
                )
            conn.commit()
            continue

        if earlier is not None:
            conn.commit()
            continue

        kind, severity = _kind_from_labels(labels)
        session_id = labels.get("session_id") or labels.get("arcnet.session_id")
        agent_id = labels.get("agent_id") or labels.get("arcnet.agent_id") or "unknown"
        annotations = alert.get("annotations") or {}
        reason = str(
            annotations.get("summary")
            or annotations.get("description")
            or labels.get("alertname")
            or "signoz alert"
        )[:500]
        row = _insert_signal(
            {
                "session_id": session_id,
                "agent_id": agent_id,
                "kind": kind,
                "severity": severity,
                "reason": reason,
                "guidance": annotations.get("description"),
                "source": "alert",
            }
        )
        _ = row
        conn.commit()
    return Response(status_code=204)


@app.get("/api/fleet")
def fleet() -> list[dict[str, Any]]:
    """Fleet Health aggregate (docs/12)."""
    conn = get_conn()
    day_ago = now_ms() - 24 * 60 * 60 * 1000
    agents = conn.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
    out: list[dict[str, Any]] = []
    for row in agents:
        a = row_to_dict(row)
        assert a is not None
        aid = a["agent_id"]
        sessions_24h = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE agent_id=? AND started_at>=?",
            (aid, day_ago),
        ).fetchone()[0]
        threats_24h = conn.execute(
            "SELECT COUNT(*) FROM threats WHERE agent_id=? AND created_at>=?",
            (aid, day_ago),
        ).fetchone()[0]
        blocked_24h = conn.execute(
            "SELECT COUNT(*) FROM threats WHERE agent_id=? AND action='block' AND created_at>=?",
            (aid, day_ago),
        ).fetchone()[0]
        active_signals = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE agent_id=? AND status IN ('pending','delivered')",
            (aid,),
        ).fetchone()[0]
        anomalies_24h = conn.execute(
            """SELECT COUNT(*) FROM signals
               WHERE agent_id=? AND source='griffin' AND created_at>=?""",
            (aid, day_ago),
        ).fetchone()[0]
        cost_rows = conn.execute(
            "SELECT usage FROM sessions WHERE agent_id=? AND started_at>=?",
            (aid, day_ago),
        ).fetchall()
        cost = 0.0
        for (usage_raw,) in cost_rows:
            if not usage_raw:
                continue
            try:
                u = json.loads(usage_raw) if isinstance(usage_raw, str) else usage_raw
                cost += float((u or {}).get("cost_usd") or 0.0)
            except Exception:  # noqa: BLE001
                pass
        out.append(
            {
                "agent_id": aid,
                "name": a.get("name"),
                "role": a.get("role"),
                "exposure": a.get("exposure"),
                "model": a.get("model"),
                "last_seen": a.get("last_seen"),
                "health": {
                    "sessions_24h": sessions_24h,
                    "threats_24h": threats_24h,
                    "blocked_24h": blocked_24h,
                    "cost_24h_usd": round(cost, 6),
                    "anomalies_24h": anomalies_24h,
                    "active_signals": active_signals,
                },
            }
        )
    return out


@app.get("/api/griffin/status")
def griffin_status() -> dict[str, Any]:
    from arcnet_server.griffin import cache_snapshot

    return cache_snapshot()


@app.post("/api/griffin/evaluate")
async def griffin_evaluate(request: Request) -> dict[str, Any]:
    """On-demand evaluate (S4 choreography) — docs/07."""
    from arcnet_server.griffin import evaluate_series

    body = await request.json()
    series_id = body.get("series_id") or "arcnet.tokens.total|agent_j"
    observed = body.get("observed")
    return evaluate_series(get_conn, series_id=series_id, observed=observed)


@app.get("/api/signoz/status")
def signoz_status() -> dict[str, Any]:
    """Seam probe: can we reach SigNoz UI? Query Range needs API key."""
    import httpx

    url = os.getenv("SIGNOZ_URL", "http://localhost:8080").rstrip("/")
    key = os.getenv("SIGNOZ_API_KEY", "").strip()
    ui_ok = False
    ui_status = None
    try:
        r = httpx.get(url, timeout=3.0, follow_redirects=True)
        ui_ok = r.status_code < 500
        ui_status = r.status_code
    except Exception as exc:  # noqa: BLE001
        ui_status = str(exc)
    query_ok = None
    query_note = "skipped: SIGNOZ_API_KEY empty"
    if key:
        try:
            r = httpx.get(
                f"{url}/api/v1/version",
                headers={"SIGNOZ-API-KEY": key},
                timeout=5.0,
            )
            query_ok = r.status_code < 400
            query_note = f"version status={r.status_code}"
        except Exception as exc:  # noqa: BLE001
            query_ok = False
            query_note = str(exc)
    return {
        "signoz_url": url,
        "ui_reachable": ui_ok,
        "ui_status": ui_status,
        "api_key_present": bool(key),
        "query_range_ok": query_ok,
        "query_note": query_note,
    }


@app.get("/api/mock/time-machine")
def mock_time_machine() -> dict[str, Any]:
    """Frozen verdict contract (docs/10) for HQ Phase 3 shell — real POST /api/replay is Phase 4."""
    return {
        "replay_id": "r_08c1",
        "session_id": "s_77b2",
        "scenario": "S4",
        "baseline": {
            "model": "gpt-4o-mini",
            "goal_reached": "killed",
            "steps": 19,
            "tool_errors": 0,
            "cost_usd": 0.062,
            "latency_ms": 41000,
        },
        "candidate": {
            "model": "gpt-4o",
            "goal_reached": "partial",
            "steps": 5,
            "tool_errors": 0,
            "cost_usd": 0.011,
            "latency_ms": 9800,
            "note": "flagged endless pagination and reported instead of looping",
        },
        "divergences": [{"step": 5, "note": "candidate stopped calling paginate_records"}],
        "verdict": "improved",
        "confidence": "3/3 runs",
        "recommendation": "route batch/reconcile tasks to gpt-4o",
    }
