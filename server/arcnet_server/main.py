"""ArcNet server — thin FastAPI routes over repository + read models (docs/12, docs/13)."""

from __future__ import annotations

import asyncio
import io
import json
import os
import secrets
import zipfile
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from arcnet_server import read_models, repository
from arcnet_server.bus import BUS
from arcnet_server.db import connect, init_db, now_ms, row_to_dict
from arcnet_server.errors import api_error, infer_hint, normalize_error_body
from arcnet_server.replay_service import execute_replay, prompt_ref

_conn = None
_griffin_task: asyncio.Task | None = None
_write_trust_logged = False

WEBHOOK_DEDUPE_MS = 5 * 60 * 1000
# Bound webhook-derived identifiers so a hostile/malformed alert cannot bloat SQLite.
WEBHOOK_ID_MAX = 128


def get_conn():
    global _conn
    if _conn is None:
        _conn = connect()
        init_db(_conn)
    return _conn


def _page_headers(response: Response, *, total: int, limit: int, offset: int) -> None:
    """Additive pagination metadata — body stays a JSON array (docs/12)."""
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)


def _require_write_secret(request: Request) -> None:
    """When ARCNET_WRITE_SECRET is set, require matching header or Bearer token."""
    expected = os.getenv("ARCNET_WRITE_SECRET", "").strip()
    if not expected:
        return
    got = (request.headers.get("x-arcnet-write-secret") or "").strip()
    if not got:
        auth = (request.headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            got = auth[7:].strip()
    if not got or not secrets.compare_digest(got, expected):
        raise HTTPException(401, "invalid or missing write secret")


def _log_localhost_trust_once() -> None:
    global _write_trust_logged
    if _write_trust_logged:
        return
    _write_trust_logged = True
    if not os.getenv("ARCNET_WRITE_SECRET", "").strip():
        print(
            "localhost-trust: writes open — set ARCNET_WRITE_SECRET or bind to 127.0.0.1",
            flush=True,
        )


async def _probe_agentos_runtime(sqlite_model: str) -> dict[str, Any]:
    """Best-effort AgentOS probe — never mutates AgentOS; honesty for reload UX."""
    base = (os.getenv("ARCNET_AGENTOS_URL") or "").strip().rstrip("/")
    if not base:
        return {
            "probed": False,
            "reachable": False,
            "sqlite_model": sqlite_model,
            "live_model": None,
            "models_match": None,
            "note": "ARCNET_AGENTOS_URL unset — skip live probe; reload still required",
        }
    url = f"{base}/internal/runtime"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(url)
        if res.status_code != 200:
            return {
                "probed": True,
                "reachable": False,
                "sqlite_model": sqlite_model,
                "live_model": None,
                "models_match": False,
                "url": url,
                "note": f"AgentOS probe HTTP {res.status_code} — restart AgentOS after apply",
            }
        body = res.json() if res.content else {}
        live = body.get("model") if isinstance(body, dict) else None
        live_s = str(live).strip() if live is not None else None
        match = live_s == sqlite_model if live_s else False
        return {
            "probed": True,
            "reachable": True,
            "sqlite_model": sqlite_model,
            "live_model": live_s,
            "models_match": match,
            "url": url,
            "note": (
                "SQLite and AgentOS process model match — new sessions should use applied model"
                if match
                else (
                    f"AgentOS still on {live_s or 'unknown'}; SQLite is {sqlite_model}. "
                    "Restart AgentOS (set ARCNET_MODEL) for new sessions to pick up apply."
                )
            ),
        }
    except Exception as exc:  # noqa: BLE001 — probe must never fail apply
        return {
            "probed": True,
            "reachable": False,
            "sqlite_model": sqlite_model,
            "live_model": None,
            "models_match": False,
            "url": url,
            "note": f"AgentOS unreachable ({type(exc).__name__}) — reload still required",
        }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _griffin_task
    get_conn()
    _log_localhost_trust_once()
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
    expose_headers=["X-Total-Count", "X-Limit", "X-Offset"],
)


@app.exception_handler(HTTPException)
async def structured_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Additive: every 404/409 includes ``detail`` + optional ``hint`` (docs/12 P8-B)."""
    body = normalize_error_body(
        status_code=exc.status_code, detail=exc.detail, path=str(request.url.path)
    )
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


def _new_id(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(4)}"


def _require_session(session_id: str) -> dict[str, Any]:
    session = repository.get_session(get_conn(), session_id)
    if session is None:
        raise api_error(
            404,
            f"session {session_id} not found",
            hint="list ids via GET /api/sessions",
        )
    return session


def _insert_signal(body: dict[str, Any], *, status: str = "pending") -> dict[str, Any]:
    signal_id = body.get("signal_id") or _new_id("sig_")
    row = repository.insert_signal(get_conn(), signal_id, body, status=status)
    BUS.publish("signal", row)
    return row


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------- write side (docs/12 ownership)


@app.post("/api/agents")
async def upsert_agent(request: Request) -> dict[str, Any]:
    _require_write_secret(request)
    body = await request.json()
    return repository.upsert_agent(get_conn(), body)


@app.post("/api/sessions")
async def upsert_session(request: Request) -> dict[str, Any]:
    _require_write_secret(request)
    body = await request.json()
    conn = get_conn()
    repository.ensure_agent(
        conn, body["agent_id"], exposure=body.get("exposure"), model=body.get("model")
    )
    session = repository.upsert_session(
        conn, {**body, "session_id": body.get("session_id") or _new_id("s_")}
    )
    return read_models.human_session(session, include_transcript=True)


@app.post("/api/threats")
async def post_threat(request: Request) -> dict[str, Any]:
    _require_write_secret(request)
    body = await request.json()
    threat_id = body.get("threat_id") or _new_id("thr_")
    row = repository.insert_threat(get_conn(), threat_id, body)
    BUS.publish("threat", row)
    return row


@app.post("/api/sources")
async def post_source(request: Request) -> dict[str, Any]:
    _require_write_secret(request)
    body = await request.json()
    source_id = body.get("source_id") or _new_id("src_")
    return repository.insert_source(get_conn(), source_id, body)


@app.post("/api/signal")
async def post_signal(request: Request) -> dict[str, Any]:
    _require_write_secret(request)
    body = await request.json()
    return _insert_signal(body)


# ---------------------------------------------------------------- human read side (dashboards)


@app.get("/api/fleet")
def fleet() -> list[dict[str, Any]]:
    """Fleet Health aggregate (docs/12)."""
    return read_models.human_fleet(repository.fleet_records(get_conn()))


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, include: str | None = Query(default=None)) -> dict[str, Any]:
    session = _require_session(session_id)
    return read_models.human_session(session, include_transcript=include == "transcript")


@app.get("/api/sessions")
def list_sessions(
    response: Response,
    scenario: str | None = None,
    agent_id: str | None = None,
    model: str | None = None,
    agent_version: str | None = None,
    version_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """Read-only session index for the UI (transcripts excluded — they're big).

    ``agent_version`` and ``version_id`` are aliases (additive) — both filter
    ``sessions.agent_version`` (stores a pinned ``agent_versions.version_id``).
    When both are set they must match.
    """
    pin = (version_id or agent_version or "").strip() or None
    if version_id and agent_version and version_id.strip() != agent_version.strip():
        raise HTTPException(400, "agent_version and version_id must match when both set")
    conn = get_conn()
    total = repository.count_sessions(
        conn, scenario=scenario, agent_id=agent_id, model=model, agent_version=pin
    )
    _page_headers(response, total=total, limit=limit, offset=offset)
    return repository.list_sessions(
        conn,
        scenario=scenario,
        agent_id=agent_id,
        model=model,
        agent_version=pin,
        limit=limit,
        offset=offset,
    )


@app.get("/api/agents/{agent_id}/models")
def list_agent_models(agent_id: str) -> list[dict[str, Any]]:
    """Distinct models for cascade pickers (docs/12 additive)."""
    conn = get_conn()
    if repository.get_agent(conn, agent_id) is None:
        raise api_error(
            404,
            f"agent {agent_id} not found",
            hint="list agents via GET /api/fleet",
        )
    return repository.list_agent_models(conn, agent_id)


@app.get("/api/agents/{agent_id}/model-intel")
def agent_model_intel(agent_id: str) -> dict[str, Any]:
    """Catalog projections + evidence-grounded recommendation (docs/27, additive endpoint)."""
    conn = get_conn()
    if repository.get_agent(conn, agent_id) is None:
        raise api_error(
            404,
            f"agent {agent_id} not found",
            hint="list agents via GET /api/fleet",
        )
    observed = repository.list_agent_models(conn, agent_id)
    return read_models.agent_model_intelligence(conn, agent_id, observed=observed)


@app.get("/api/agents/{agent_id}/versions/timeline")
def agent_versions_timeline(agent_id: str) -> dict[str, Any]:
    """HQ Agent version timeline (docs/18)."""
    return repository.agent_version_timeline(get_conn(), agent_id)


@app.get("/api/agents/{agent_id}/versions")
def list_agent_versions(
    agent_id: str,
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    conn = get_conn()
    total = repository.count_agent_versions(conn, agent_id)
    _page_headers(response, total=total, limit=limit, offset=offset)
    return repository.list_agent_versions(conn, agent_id, limit=limit, offset=offset)


def _require_session_for_agent(conn: Any, session_id: str, agent_id: str) -> dict[str, Any]:
    """Session must exist and belong to agent_id (blocks cross-agent pins)."""
    sess = repository.get_session(conn, session_id)
    if sess is None:
        raise api_error(
            404,
            f"session {session_id} not found",
            hint="list ids via GET /api/sessions",
        )
    if sess.get("agent_id") != agent_id:
        raise HTTPException(
            400,
            f"session {session_id} belongs to agent {sess.get('agent_id')}, not {agent_id}",
        )
    return sess


def _require_hq_proposal_for_agent(conn: Any, proposal_signal_id: str, agent_id: str) -> dict[str, Any]:
    """Proposal must exist, be source=hq_agent, and belong to agent_id."""
    sig = conn.execute(
        "SELECT * FROM signals WHERE signal_id=?", (proposal_signal_id,)
    ).fetchone()
    prop = row_to_dict(sig)
    if prop is None:
        raise api_error(
            404,
            f"proposal {proposal_signal_id} not found",
            hint="list hq_agent proposals via GET /api/signals?source=hq_agent",
        )
    if prop.get("source") != "hq_agent":
        raise HTTPException(400, f"proposal {proposal_signal_id} is not source=hq_agent")
    if prop.get("agent_id") != agent_id:
        raise HTTPException(
            400,
            f"proposal {proposal_signal_id} belongs to agent {prop.get('agent_id')}, not {agent_id}",
        )
    return prop


@app.post("/api/agents/{agent_id}/versions")
async def create_agent_version(agent_id: str, request: Request) -> dict[str, Any]:
    _require_write_secret(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")
    version = body.get("version")
    if not version or not str(version).strip():
        raise HTTPException(400, "version is required")
    version_id = body.get("version_id") or _new_id("av_")
    conn = get_conn()
    session_id = body.get("session_id")
    if session_id is not None:
        session_id = str(session_id).strip() or None
        if session_id:
            _require_session_for_agent(conn, session_id, agent_id)
    return repository.insert_agent_version(
        conn,
        version_id,
        agent_id,
        {
            "version": str(version).strip(),
            "model": body.get("model"),
            "model_version": body.get("model_version"),
            "source_ref": body.get("source_ref"),
            "notes": body.get("notes"),
            "session_id": session_id,
        },
    )


@app.post("/api/agents/{agent_id}/apply-model")
async def apply_agent_model(agent_id: str, request: Request) -> dict[str, Any]:
    """Human-gated model apply — requires confirm:true; records a version bump."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a JSON object")
    if body.get("confirm") is not True:
        raise HTTPException(
            400,
            "confirm: true is required (human-gated; no silent model swaps)",
        )
    model = body.get("model")
    version = body.get("version")
    if not model or not str(model).strip():
        raise HTTPException(400, "model is required")
    if not version or not str(version).strip():
        raise HTTPException(400, "version is required")
    conn = get_conn()
    if repository.get_agent(conn, agent_id) is None:
        raise api_error(
            404,
            f"agent {agent_id} not found",
            hint="list agents via GET /api/fleet",
        )
    session_id = body.get("session_id")
    if session_id is not None:
        session_id = str(session_id).strip() or None
        if session_id:
            _require_session_for_agent(conn, session_id, agent_id)
    proposal_signal_id = body.get("proposal_signal_id")
    if proposal_signal_id is not None:
        proposal_signal_id = str(proposal_signal_id).strip() or None
        if proposal_signal_id:
            _require_hq_proposal_for_agent(conn, proposal_signal_id, agent_id)
    version_id = body.get("version_id") or _new_id("av_")
    applied_model = str(model).strip()
    try:
        out = repository.apply_agent_model(
            conn,
            agent_id,
            version_id,
            model=applied_model,
            version=str(version).strip(),
            model_version=body.get("model_version"),
            source_ref=body.get("source_ref"),
            notes=body.get("notes") or "applied via POST /api/agents/.../apply-model",
            session_id=session_id,
            proposal_signal_id=proposal_signal_id,
        )
    except repository.ApplyModelError as exc:
        msg = str(exc)
        if "already exists" in msg:
            raise api_error(
                409,
                msg,
                hint="omit version_id to auto-generate or pick a fresh version_id",
            ) from exc
        raise HTTPException(400, msg) from exc
    # Best-effort probe — never blocks apply; informs HQ reload banner.
    probe = await _probe_agentos_runtime(applied_model)
    out["agentos_probe"] = probe
    # Clear contradictory reload flag when live AgentOS already matches SQLite.
    if probe.get("models_match") is True:
        out["agentos_reload_required"] = False
        out["agentos_reload_instructions"] = (
            "SQLite and live AgentOS process model already match — "
            "no AgentOS restart needed for new sessions."
        )
    return out


@app.get("/api/threats")
def list_threats(
    response: Response,
    since: int | None = None,
    agent_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    conn = get_conn()
    total = repository.count_threats(conn, since=since, agent_id=agent_id)
    _page_headers(response, total=total, limit=limit, offset=offset)
    return repository.list_threats(
        conn, since=since, agent_id=agent_id, limit=limit, offset=offset
    )


@app.get("/api/sources")
def list_sources(
    response: Response,
    agent_id: str | None = None,
    session_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    conn = get_conn()
    total = repository.count_sources(conn, agent_id=agent_id, session_id=session_id)
    _page_headers(response, total=total, limit=limit, offset=offset)
    return repository.list_sources(
        conn,
        agent_id=agent_id,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )


@app.get("/api/signals")
def list_signals(
    response: Response,
    session_id: str | None = None,
    agent_id: str | None = None,
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    conn = get_conn()
    total = repository.count_signals(
        conn, session_id=session_id, agent_id=agent_id, source=source
    )
    _page_headers(response, total=total, limit=limit, offset=offset)
    return repository.list_signals(
        conn,
        session_id=session_id,
        agent_id=agent_id,
        source=source,
        limit=limit,
        offset=offset,
    )


@app.get("/api/replays")
def list_replays(
    response: Response,
    session_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    conn = get_conn()
    total = repository.count_replays(conn, session_id=session_id)
    _page_headers(response, total=total, limit=limit, offset=offset)
    return repository.list_replays(
        conn, session_id=session_id, limit=limit, offset=offset
    )


# ---------------------------------------------------------------- time machine


@app.post("/api/replay")
async def post_replay(request: Request) -> dict[str, Any]:
    """Replay one SQLite-primary recording three times against one candidate."""
    body = await request.json()
    session_id = body.get("session_id")
    candidate_model = body.get("candidate_model")
    candidate_prompt = body.get("candidate_prompt")
    if not session_id:
        raise HTTPException(400, "session_id is required")
    if bool(candidate_model) == bool(candidate_prompt):
        raise HTTPException(400, "provide exactly one of candidate_model or candidate_prompt")

    session = _require_session(str(session_id))
    if not session.get("transcript"):
        raise HTTPException(422, f"session {session_id} has no replay-ready transcript")
    model = str(candidate_model or session.get("model") or "")
    if not model:
        raise HTTPException(422, "candidate prompt replay requires a recorded model")

    replay_id = _new_id("r_")

    def progress(phase: str, step: int, total_steps: int) -> None:
        BUS.publish(
            "replay_progress",
            {
                "replay_id": replay_id,
                "step": step,
                "total_steps": total_steps,
                "phase": phase,
            },
        )

    try:
        runs, verdict, duration_ms = await execute_replay(
            replay_id=replay_id,
            session=session,
            candidate_model=model,
            candidate_prompt=str(candidate_prompt) if candidate_prompt else None,
            progress=progress,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"agent replay runtime unavailable: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    repository.insert_replay(
        get_conn(),
        {
            "replay_id": replay_id,
            "session_id": session_id,
            "candidate_model": model if candidate_model else None,
            "candidate_prompt_ref": prompt_ref(str(candidate_prompt)) if candidate_prompt else None,
            "runs": runs,
            "verdict": verdict,
            "duration_ms": duration_ms,
        },
    )
    return verdict


# ---------------------------------------------------------------- agent read side (machine twins)


@app.get("/api/agent-view/replay/{replay_id}")
def replay_agent_view(replay_id: str) -> dict[str, Any]:
    replay = repository.get_replay(get_conn(), replay_id)
    if replay is None:
        raise api_error(
            404,
            f"replay {replay_id} not found",
            hint="list replays via GET /api/replays?session_id=<session_id>",
        )
    session_id = replay.get("session_id")
    session = repository.get_session(get_conn(), str(session_id)) if session_id else None
    agent_id = (session or {}).get("agent_id")
    return read_models.envelope(
        "replay",
        replay_id,
        replay["verdict"],
        trace_id=replay.get("trace_id"),
        human_view=f"/time-machine/{replay_id}",
        extra_links=read_models.graph_links(
            agent_id=str(agent_id) if agent_id else None,
            session_id=str(session_id) if session_id else None,
            replay_id=replay_id,
        ),
    )


@app.get("/api/agent-view/{view}/{id}")
def agent_view(view: str, id: str) -> dict[str, Any]:
    """Machine-optimal twin of any HQ view (docs/12). replay has its own route."""
    conn = get_conn()

    def _no_ref() -> None:
        raise api_error(
            404,
            f"no agent or session '{id}'",
            hint="list sessions via GET /api/sessions or agents via GET /api/fleet",
        )

    if view == "home":
        if id != "all":
            raise api_error(
                404,
                f"unknown home scope '{id}' (use all)",
                hint="use id=all",
            )
        data = read_models.agent_home_data(conn)
        return read_models.envelope(
            "home",
            id,
            data,
            trace_id=None,
            human_view="/",
            extra_links={
                "fleet_health": "/api/agent-view/fleet_health/all",
                "griffin_status": "/api/griffin/status",
            },
        )

    if view in ("fleet", "fleet_health"):
        view_name = "fleet_health" if view == "fleet_health" else "fleet"
        data = read_models.agent_fleet_health_data(conn)
        return read_models.envelope(
            view_name,
            id,
            data,
            trace_id=None,
            human_view="/fleet_health",
            extra_links={"threats": "/api/agent-view/threats/all"},
        )

    if view in ("sources", "sources_trust"):
        view_name = "sources_trust" if view == "sources_trust" else "sources"
        if not repository.session_or_agent_exists(conn, id):
            _no_ref()
        session = repository.get_session(conn, id)
        agent = repository.get_agent(conn, id)
        data = read_models.agent_sources_data(conn, ref_id=id)
        return read_models.envelope(
            view_name,
            id,
            data,
            trace_id=session.get("trace_id") if session else None,
            human_view="/sources_trust",
            extra_links=read_models.graph_links(
                agent_id=str(agent["agent_id"]) if agent else None,
                session_id=str(session["session_id"]) if session else None,
            ),
        )

    if view == "threats":
        try:
            data = read_models.agent_threats_data(conn, ref_id=id)
        except LookupError:
            _no_ref()
        session = repository.get_session(conn, id) if id != "all" else None
        agent = repository.get_agent(conn, id) if id != "all" and session is None else None
        return read_models.envelope(
            "threats",
            id,
            data,
            trace_id=session.get("trace_id") if session else None,
            human_view="/fleet_health",
            extra_links=read_models.graph_links(
                agent_id=str(agent["agent_id"]) if agent else (id if data["scope"] == "agent" else None),
                session_id=str(session["session_id"]) if session else (id if data["scope"] == "session" else None),
            ),
        )

    if view == "hitl":
        if id != "all" and repository.get_session(conn, id) is None:
            raise api_error(
                404,
                f"session {id} not found",
                hint="list ids via GET /api/sessions or use id=all",
            )
        data = read_models.agent_hitl_data(conn, ref_id=id)
        session = repository.get_session(conn, id) if id != "all" else None
        return read_models.envelope(
            "hitl",
            id,
            data,
            trace_id=session.get("trace_id") if session else None,
            human_view="/hitl",
            extra_links=read_models.graph_links(
                session_id=str(session["session_id"]) if session else None,
            ),
        )

    if view == "hq_agent":
        try:
            data = read_models.agent_hq_agent_data(conn, agent_id=id)
        except LookupError:
            raise api_error(
                404,
                f"agent {id} not found",
                hint="list agents via GET /api/fleet",
            )
        return read_models.envelope(
            "hq_agent",
            id,
            data,
            trace_id=None,
            human_view="/hq_agent",
            extra_links=read_models.graph_links(agent_id=id),
        )

    if view == "case_files":
        session = _require_session(id)
        agent_id = session.get("agent_id")
        replay = repository.latest_replay_for_session(conn, id)
        data = read_models.agent_case_files_data(conn, session)
        return read_models.envelope(
            "case_files",
            id,
            data,
            trace_id=session.get("trace_id"),
            human_view="/case_files",
            extra_links=read_models.graph_links(
                agent_id=str(agent_id) if agent_id else None,
                session_id=id,
                replay_id=replay.get("replay_id") if replay else None,
            ),
        )

    if view == "time_machine":
        try:
            data = read_models.agent_time_machine_data(conn, ref_id=id)
        except LookupError:
            raise api_error(
                404,
                f"no replay or session '{id}'",
                hint="list sessions via GET /api/sessions or replays via GET /api/replays",
            )
        session = repository.get_session(conn, id)
        replay = repository.get_replay(conn, id)
        sid = data.get("session_id") or (session or {}).get("session_id") or id
        sess_row = repository.get_session(conn, str(sid)) if sid else None
        agent_id = (sess_row or {}).get("agent_id")
        return read_models.envelope(
            "time_machine",
            id,
            data,
            trace_id=(sess_row or {}).get("trace_id"),
            human_view="/time_machine",
            extra_links=read_models.graph_links(
                agent_id=str(agent_id) if agent_id else None,
                session_id=str(sid) if sid else None,
                replay_id=id if replay else data.get("latest_replay_id"),
            ),
        )

    if view == "incident":
        return read_models.incident_envelope(conn, _require_session(id))

    if view == "session":
        session = _require_session(id)
        agent_id = session.get("agent_id")
        return read_models.envelope(
            "session",
            id,
            read_models.agent_session_context(session),
            trace_id=session.get("trace_id"),
            human_view=f"/sessions/{id}",
            extra_links=read_models.graph_links(
                agent_id=str(agent_id) if agent_id else None,
                session_id=id,
            ),
        )

    if view == "check":
        session = _require_session(id)
        agent_id = session.get("agent_id")
        return read_models.envelope(
            "check",
            id,
            read_models.session_check_data(conn, session),
            trace_id=session.get("trace_id"),
            human_view=f"/sessions/{id}",
            extra_links=read_models.graph_links(
                agent_id=str(agent_id) if agent_id else None,
                session_id=id,
            ),
        )

    if view == "signals":
        if id == "all":
            data = read_models.agent_signals_fleet_data(conn)
            return read_models.envelope(
                "signals",
                id,
                data,
                trace_id=None,
                human_view="/signals",
            )
        session = repository.get_session(conn, id)
        agent = repository.get_agent(conn, id)
        if session is None and agent is None:
            _no_ref()
        is_session = session is not None
        data = read_models.agent_signals_data(conn, ref_id=id, is_session=is_session)
        return read_models.envelope(
            "signals",
            id,
            data,
            trace_id=session.get("trace_id") if session else None,
            human_view="/signals" if not is_session else f"/signals?session={id}",
            extra_links=read_models.graph_links(
                agent_id=str(agent["agent_id"]) if agent else None,
                session_id=str(session["session_id"]) if session else None,
            ),
        )

    if view == "dashboards":
        if id not in ("all", "status"):
            raise api_error(
                404,
                f"unknown dashboards scope '{id}' (use all or status)",
                hint="use id=all or id=status",
            )
        status = _signoz_status_payload()
        data = {
            "signoz": status,
            "note": (
                "HQ dashboards are a launcher + status probe. "
                "Use SigNoz UI deep-links or SigNoz MCP for query depth."
            ),
            "status_api": "/api/signoz/status",
            "links": {
                "signoz_ui": status.get("signoz_url"),
                "status_api": "/api/signoz/status",
            },
        }
        return read_models.envelope(
            "dashboards",
            id,
            data,
            trace_id=None,
            human_view="/dashboards",
            extra_links={
                "signoz_ui": status.get("signoz_url"),
                "signoz_status": "/api/signoz/status",
            },
        )

    raise api_error(
        404,
        f"unknown agent-view '{view}'",
        hint=infer_hint(status_code=404, detail=f"unknown agent-view '{view}'", path=f"/api/agent-view/{view}/{id}"),
    )


# ---------------------------------------------------------------- case file


def _case_file_zip_bytes(session_id: str) -> tuple[bytes, str, dict[str, Any]]:
    """Build the Case File bundle (docs/12). Returns (zip_bytes, markdown, envelope)."""
    session = _require_session(session_id)
    env = read_models.incident_envelope(get_conn(), session)
    md = read_models.case_file_markdown(env, session)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("case-file.md", md)
        zf.writestr("case-file.json", json.dumps(env, indent=2))
    return buf.getvalue(), md, env


@app.get("/export/case-file/{session_id}")
def export_case_file(session_id: str):
    """Case File bundle: case-file.md + case-file.json (docs/12)."""
    payload, _md, _env = _case_file_zip_bytes(session_id)
    headers = {"Content-Disposition": f'attachment; filename="case-file-{session_id}.zip"'}
    return StreamingResponse(io.BytesIO(payload), media_type="application/zip", headers=headers)


# ---------------------------------------------------------------- SSE


@app.get("/signals/stream")
async def signals_stream(
    request: Request,
    session_id: str | None = None,
) -> EventSourceResponse:
    """SSE firehose / per-session stream with Last-Event-ID replay (docs/12)."""

    async def gen():
        # Replay missed rows from tables when Last-Event-ID present
        last = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
        if last and last.isdigit():
            # Best-effort: event ids are bus seq, not signal_ids. On reconnect,
            # dump the last 50 rows matching the same attribution rule as live.
            rows = repository.list_signals(get_conn(), session_id=session_id, limit=50)
            for d in reversed(rows):
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
                if ev.event == "signal" and not repository.signal_matches_session(
                    ev.data or {}, session_id
                ):
                    continue
                yield {
                    "event": ev.event,
                    "id": ev.event_id,
                    "data": json.dumps(ev.data),
                }
        finally:
            BUS.unsubscribe(q)

    return EventSourceResponse(gen())


# ---------------------------------------------------------------- hitl


@app.get("/api/hitl")
def list_hitl(
    response: Response,
    session_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """List HITL approval rows (newest first)."""
    conn = get_conn()
    total = repository.count_hitl(conn, session_id=session_id, status=status)
    _page_headers(response, total=total, limit=limit, offset=offset)
    return repository.list_hitl(
        conn, session_id=session_id, status=status, limit=limit, offset=offset
    )


@app.post("/api/hitl")
async def create_hitl(request: Request) -> dict[str, Any]:
    """Create a HITL approval row (pause scaffold)."""
    body = await request.json()
    hitl_id = body.get("hitl_id") or _new_id("hitl_")
    row = repository.insert_hitl(get_conn(), hitl_id, body)
    BUS.publish("hitl_request", row)
    return row


@app.post("/api/hitl/{hitl_id}")
async def decide_hitl(hitl_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    decision = body.get("decision")
    if decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be approved|rejected")
    conn = get_conn()
    if repository.get_hitl(conn, hitl_id) is None:
        raise api_error(
            404,
            f"hitl {hitl_id} not found",
            hint="list rows via GET /api/hitl",
        )
    row = repository.decide_hitl(conn, hitl_id, decision)
    BUS.publish("hitl_request", row)
    return row


# ---------------------------------------------------------------- webhook


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


def _clip_id(value: Any, *, default: str | None = None) -> str | None:
    """Truncate webhook label ids; empty → default (None stays None when default is None)."""
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text[:WEBHOOK_ID_MAX]


@app.post("/webhooks/signoz")
async def signoz_webhook(request: Request):
    """SigNoz alert webhook — dedupe + map labels → Signal (docs/12).

    Local-by-design in v1. Optional shared secret: set ARCNET_WEBHOOK_SECRET and
    send header ``X-ArcNet-Webhook-Secret`` (or ``Authorization: Bearer …``).
    When the env is empty, any caller who can reach :8000 can inject signals —
    bind to localhost in production-ish deploys.
    """
    expected = os.getenv("ARCNET_WEBHOOK_SECRET", "").strip()
    if expected:
        got = (request.headers.get("x-arcnet-webhook-secret") or "").strip()
        if not got:
            auth = (request.headers.get("authorization") or "").strip()
            if auth.lower().startswith("bearer "):
                got = auth[7:].strip()
        if not got or not secrets.compare_digest(got, expected):
            raise HTTPException(401, "invalid or missing webhook secret")
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "webhook body must be JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(400, "webhook body must be a JSON object")

    conn = get_conn()
    raw_alerts = body.get("alerts")
    alerts: list[Any]
    if raw_alerts is None:
        alerts = [body]
    elif isinstance(raw_alerts, list):
        alerts = raw_alerts
    else:
        raise HTTPException(400, "alerts must be a list when present")
    overall = str(body.get("status") or "").lower()

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        labels = dict(alert.get("labels") or {})
        fingerprint = _clip_id(
            alert.get("fingerprint") or labels.get("alertname"), default="unknown"
        ) or "unknown"
        status = str(alert.get("status") or overall or "firing").lower()

        seen = repository.webhook_seen_recently(conn, fingerprint, window_ms=WEBHOOK_DEDUPE_MS)
        repository.insert_webhook_event(conn, fingerprint, status, alert)

        if status in ("resolved", "ok"):
            agent_id = _clip_id(labels.get("agent_id") or labels.get("arcnet.agent_id"))
            if agent_id:
                repository.expire_alert_signals(conn, agent_id, window_ms=WEBHOOK_DEDUPE_MS)
            conn.commit()
            continue

        if seen:
            conn.commit()
            continue

        kind, severity = _kind_from_labels(labels)
        annotations = alert.get("annotations") or {}
        reason = str(
            annotations.get("summary")
            or annotations.get("description")
            or labels.get("alertname")
            or "signoz alert"
        )[:500]
        _insert_signal(
            {
                "session_id": _clip_id(
                    labels.get("session_id") or labels.get("arcnet.session_id")
                ),
                "agent_id": _clip_id(
                    labels.get("agent_id") or labels.get("arcnet.agent_id"),
                    default="unknown",
                )
                or "unknown",
                "kind": kind,
                "severity": severity,
                "reason": reason,
                "guidance": annotations.get("description"),
                "source": "alert",
            }
        )
        conn.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- griffin + seam probes


@app.get("/api/griffin/status")
def griffin_status() -> dict[str, Any]:
    """Griffin MAD status — warmth, estimator, last anomaly, series source (Wave B)."""
    from arcnet_server.griffin import cache_snapshot, ensure_series_warm

    try:
        ensure_series_warm(get_conn)
    except Exception:  # noqa: BLE001
        pass
    return cache_snapshot()


@app.post("/api/griffin/evaluate")
async def griffin_evaluate(request: Request) -> dict[str, Any]:
    """On-demand evaluate (S4 choreography) — docs/07."""
    from arcnet_server.griffin import evaluate_series

    body = await request.json()
    series_id = body.get("series_id") or "arcnet.tokens.total|agent_j"
    observed = body.get("observed")
    return evaluate_series(get_conn, series_id=series_id, observed=observed)


def _signoz_dashboard_map(url: str, key: str) -> dict[str, str | None]:
    """Resolve ArcNet dashboard UUIDs from env overrides and/or SigNoz list API.

    Titles match deploy/provision templates. Env wins when set:
    SIGNOZ_DASHBOARD_FLEET / _THREATS / _COST / _AGNO.
    """
    keys = {
        "fleet_ops": "SIGNOZ_DASHBOARD_FLEET",
        "threats_trust": "SIGNOZ_DASHBOARD_THREATS",
        "cost_tokens": "SIGNOZ_DASHBOARD_COST",
        "agno": "SIGNOZ_DASHBOARD_AGNO",
    }
    out: dict[str, str | None] = {k: (os.getenv(env) or "").strip() or None for k, env in keys.items()}
    title_to_slot = {
        "ArcNet Fleet Ops": "fleet_ops",
        "ArcNet Threats & Trust": "threats_trust",
        "ArcNet Cost & Tokens": "cost_tokens",
        "Agno": "agno",
    }
    if not key or all(out.values()):
        return out
    try:
        r = httpx.get(
            f"{url}/api/v1/dashboards",
            headers={"SIGNOZ-API-KEY": key},
            timeout=5.0,
        )
        if r.status_code >= 400:
            return out
        payload = r.json()
        items = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            items = payload if isinstance(payload, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            did = item.get("id")
            data = item.get("data") if isinstance(item.get("data"), dict) else item
            title = data.get("title") if isinstance(data, dict) else None
            if not isinstance(did, str) or not isinstance(title, str):
                continue
            slot = title_to_slot.get(title)
            if slot and not out[slot]:
                out[slot] = did
    except Exception:  # noqa: BLE001
        return out
    return out


@app.get("/api/signoz/status")
def signoz_status() -> dict[str, Any]:
    """Seam probe: UI reachability + authenticated Query Range smoke (docs/04)."""
    return _signoz_status_payload()


@app.get("/api/signoz/evidence")
def signoz_evidence(session_id: str = Query(..., min_length=1)) -> dict[str, Any]:
    """Bounded SigNoz evidence for a session — ids/spans/token counts only (Wave B).

    No full payloads. Degrades honestly when API key missing or Query Range fails.
    """
    return _signoz_evidence_payload(session_id.strip())


def _signoz_evidence_payload(session_id: str) -> dict[str, Any]:
    url = os.getenv("SIGNOZ_URL", "http://localhost:8080").rstrip("/")
    key = os.getenv("SIGNOZ_API_KEY", "").strip()
    conn = get_conn()
    sess = repository.get_session(conn, session_id)
    if sess is None:
        raise api_error(
            404,
            f"session {session_id} not found",
            hint="list ids via GET /api/sessions",
        )
    trace_id = sess.get("trace_id")
    out: dict[str, Any] = {
        "session_id": session_id,
        "agent_id": sess.get("agent_id"),
        "trace_id": trace_id,
        "signoz_url": url,
        "api_key_present": bool(key),
        "links": {
            "signoz_trace": f"{url}/trace/{trace_id}" if trace_id else None,
            "status": "/api/signoz/status",
        },
        "spans": [],
        "truncated": False,
        "note": None,
        "mcp_fallback": (
            "Prefer this HTTP evidence endpoint + Case File links.signoz_trace + "
            "Query Range curl before SigNoz MCP. MCP stdio may hang — do not block on it."
        ),
    }
    if not key:
        out["note"] = "SIGNOZ_API_KEY empty — SQLite session metadata only"
        usage = sess.get("usage") if isinstance(sess.get("usage"), dict) else {}
        if usage:
            out["usage_excerpt"] = {
                k: usage.get(k)
                for k in ("total_tokens", "prompt_tokens", "completion_tokens", "cost_usd")
                if k in usage
            }
        return out
    if not trace_id:
        out["note"] = "no trace_id on session — cannot query SigNoz spans"
        return out
    end = now_ms()
    start = end - 7 * 24 * 60 * 60 * 1000  # 7d window
    # Prefer filter on arcnet.session_id; fall back to trace id attribute if present
    expression = f"traceID = '{trace_id}'"
    payload = {
        "start": start,
        "end": end,
        "requestType": "raw",
        "compositeQuery": {
            "queries": [
                {
                    "type": "builder_query",
                    "spec": {
                        "name": "A",
                        "signal": "traces",
                        "stepInterval": 60,
                        "disabled": False,
                        "filter": {"expression": expression},
                        "limit": 8,
                        "offset": 0,
                        "order": [{"key": {"name": "timestamp"}, "direction": "desc"}],
                        "having": {"expression": ""},
                        "selectFields": [
                            {
                                "name": "name",
                                "fieldDataType": "string",
                                "signal": "traces",
                                "fieldContext": "span",
                            },
                            {
                                "name": "durationNano",
                                "fieldDataType": "float64",
                                "signal": "traces",
                                "fieldContext": "span",
                            },
                        ],
                    },
                }
            ]
        },
    }
    try:
        r = httpx.post(
            f"{url}/api/v5/query_range",
            headers={"SIGNOZ-API-KEY": key, "Content-Type": "application/json"},
            json=payload,
            timeout=10.0,
        )
        if r.status_code >= 400:
            out["note"] = f"query_range status={r.status_code}"
            out["query_ok"] = False
            return out
        body = r.json()
        spans = _extract_bounded_spans(body, max_spans=8)
        out["spans"] = spans
        out["query_ok"] = True
        out["truncated"] = len(spans) >= 8
        out["note"] = "bounded span names + durations only — no payloads"
    except Exception as exc:  # noqa: BLE001
        out["query_ok"] = False
        out["note"] = f"query_range failed: {str(exc)[:200]}"
    return out


def _is_span_like(node: dict[str, Any]) -> bool:
    """True only for real span rows — not query/column metadata with a bare name."""
    name = node.get("name") or node.get("spanName")
    if not isinstance(name, str) or not name.strip():
        return False
    has_dur = any(
        node.get(k) is not None for k in ("durationNano", "duration_ns", "duration")
    )
    has_id = any(
        isinstance(node.get(k), str) and node.get(k)
        for k in ("spanId", "span_id", "spanID", "traceId", "trace_id", "traceID")
    )
    # SigNoz span rows carry duration and/or ids; named metadata alone is not a span
    return has_dur or has_id


def _extract_bounded_spans(body: Any, *, max_spans: int = 8) -> list[dict[str, Any]]:
    """Pull span name/duration pointers from Query Range JSON — never full attrs."""
    spans: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if len(spans) >= max_spans:
            return
        if isinstance(node, dict):
            if _is_span_like(node):
                name = node.get("name") or node.get("spanName")
                dur = (
                    node.get("durationNano")
                    or node.get("duration_ns")
                    or node.get("duration")
                )
                entry: dict[str, Any] = {"name": str(name)[:120]}
                if dur is not None:
                    try:
                        entry["duration_ns"] = int(dur)
                    except (TypeError, ValueError):
                        pass
                sid = (
                    node.get("spanId")
                    or node.get("span_id")
                    or node.get("spanID")
                )
                if isinstance(sid, str) and sid:
                    entry["span_id"] = sid[:64]
                # Avoid dumping nested payloads
                spans.append(entry)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(body)
    # Dedupe by name keeping first
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for s in spans:
        n = s.get("name") or ""
        if n in seen:
            continue
        seen.add(n)
        out.append(s)
        if len(out) >= max_spans:
            break
    return out


def _signoz_status_payload() -> dict[str, Any]:
    """Shared SigNoz probe for /api/signoz/status and agent-view/dashboards."""
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
        # Tiny authenticated builder query — proves the key works for Query Range,
        # not merely that /api/v1/version is reachable.
        end = now_ms()
        start = end - 60_000
        payload = {
            "start": start,
            "end": end,
            "requestType": "raw",
            "compositeQuery": {
                "queries": [
                    {
                        "type": "builder_query",
                        "spec": {
                            "name": "A",
                            "signal": "traces",
                            "stepInterval": 60,
                            "disabled": False,
                            "filter": {"expression": ""},
                            "limit": 1,
                            "offset": 0,
                            "order": [{"key": {"name": "timestamp"}, "direction": "desc"}],
                            "having": {"expression": ""},
                            "selectFields": [
                                {
                                    "name": "name",
                                    "fieldDataType": "string",
                                    "signal": "traces",
                                    "fieldContext": "span",
                                }
                            ],
                        },
                    }
                ]
            },
        }
        try:
            r = httpx.post(
                f"{url}/api/v5/query_range",
                headers={"SIGNOZ-API-KEY": key, "Content-Type": "application/json"},
                json=payload,
                timeout=8.0,
            )
            query_ok = r.status_code < 400
            query_note = f"query_range status={r.status_code}"
        except Exception as exc:  # noqa: BLE001
            query_ok = False
            query_note = str(exc)
    dashboards = _signoz_dashboard_map(url, key)
    return {
        "signoz_url": url,
        "ui_reachable": ui_ok,
        "ui_status": ui_status,
        "api_key_present": bool(key),
        "query_range_ok": query_ok,
        "query_note": query_note,
        "dashboards": dashboards,
        "mcp_note": (
            "Prefer HTTP: /api/signoz/evidence + Case File links.signoz_trace + "
            "Query Range curl. SigNoz MCP stdio may hang (G5 PARTIAL) — optional only."
        ),
    }
