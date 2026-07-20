"""ArcNet server — SQLite + Phase 1 write/read routes (docs/12)."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from arcnet_server.db import connect, dumps, init_db, now_ms, row_to_dict

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = connect()
        init_db(_conn)
    return _conn


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_conn()
    yield


app = FastAPI(title="arcnet-server", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _new_id(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(4)}"


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
    # Ensure agent exists (minimal upsert)
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
            "pending",
            ts,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM signals WHERE signal_id=?", (signal_id,)).fetchone()
    return row_to_dict(row)  # type: ignore[return-value]


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
    return row_to_dict(row)  # type: ignore[return-value]


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
