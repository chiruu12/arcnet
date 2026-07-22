"""Query/write primitives — the only module that speaks SQL (docs/13).

Every function takes an open connection, returns plain dict records (JSON
columns parsed), and orders deterministically (timestamp DESC, id DESC) so
pagination and demo output are stable. Read models project these records for
the human and agent audiences; routes never embed SQL.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from arcnet_server.db import dumps, now_ms, row_to_dict

DAY_MS = 24 * 60 * 60 * 1000

# ---------------------------------------------------------------- agents


def get_agent(conn: sqlite3.Connection, agent_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    return row_to_dict(row)


def upsert_agent(conn: sqlite3.Connection, fields: dict[str, Any]) -> dict[str, Any]:
    agent_id = fields["agent_id"]
    ts = now_ms()
    if get_agent(conn, agent_id):
        conn.execute(
            "UPDATE agents SET name=?, role=?, exposure=?, model=?, last_seen=? WHERE agent_id=?",
            (
                fields.get("name") or agent_id,
                fields.get("role"),
                fields.get("exposure") or "internal",
                fields.get("model"),
                ts,
                agent_id,
            ),
        )
    else:
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
            (
                agent_id,
                fields.get("name") or agent_id,
                fields.get("role"),
                fields.get("exposure") or "internal",
                fields.get("model"),
                ts,
                ts,
            ),
        )
    conn.commit()
    agent = get_agent(conn, agent_id)
    assert agent is not None
    return agent


def ensure_agent(conn: sqlite3.Connection, agent_id: str, *, exposure: str | None, model: str | None) -> None:
    if get_agent(conn, agent_id) is None:
        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, exposure, model, first_seen, last_seen) VALUES (?,?,?,?,?,?)",
            (agent_id, agent_id, exposure or "internal", model, ts, ts),
        )


def set_agent_model(conn: sqlite3.Connection, agent_id: str, model: str) -> dict[str, Any]:
    """Update the agent's current model (human-gated apply path)."""
    ensure_agent(conn, agent_id, exposure=None, model=model)
    conn.execute(
        "UPDATE agents SET model=?, last_seen=? WHERE agent_id=?",
        (model, now_ms(), agent_id),
    )
    conn.commit()
    agent = get_agent(conn, agent_id)
    assert agent is not None
    return agent


def set_session_agent_version(
    conn: sqlite3.Connection,
    session_id: str,
    agent_version: str,
) -> dict[str, Any] | None:
    """Pin a session row to an agent_versions.version_id or version tag."""
    if get_session(conn, session_id) is None:
        return None
    conn.execute(
        "UPDATE sessions SET agent_version=? WHERE session_id=?",
        (agent_version, session_id),
    )
    conn.commit()
    return get_session(conn, session_id)


def fleet_records(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Agents + 24h health aggregates in one pass (no per-agent query loop)."""
    day_ago = now_ms() - DAY_MS
    agents = [
        row_to_dict(r)
        for r in conn.execute(
            "SELECT * FROM agents ORDER BY last_seen DESC, agent_id ASC"
        ).fetchall()
    ]

    def counts(query: str, params: tuple[Any, ...]) -> dict[str, int]:
        return {row[0]: row[1] for row in conn.execute(query, params).fetchall()}

    sessions_24h = counts(
        "SELECT agent_id, COUNT(*) FROM sessions WHERE started_at>=? GROUP BY agent_id",
        (day_ago,),
    )
    threats_24h = counts(
        "SELECT agent_id, COUNT(*) FROM threats WHERE created_at>=? GROUP BY agent_id",
        (day_ago,),
    )
    blocked_24h = counts(
        "SELECT agent_id, COUNT(*) FROM threats WHERE action='block' AND created_at>=? GROUP BY agent_id",
        (day_ago,),
    )
    anomalies_24h = counts(
        "SELECT agent_id, COUNT(*) FROM signals WHERE source='griffin' AND created_at>=? GROUP BY agent_id",
        (day_ago,),
    )
    active_signals = counts(
        "SELECT agent_id, COUNT(*) FROM signals WHERE status IN ('pending','delivered') GROUP BY agent_id",
        (),
    )
    cost_24h = {
        row[0]: float(row[1] or 0.0)
        for row in conn.execute(
            """SELECT agent_id,
                      SUM(CASE WHEN json_valid(usage)
                          THEN COALESCE(json_extract(usage, '$.cost_usd'), 0) ELSE 0 END)
               FROM sessions WHERE started_at>=? GROUP BY agent_id""",
            (day_ago,),
        ).fetchall()
    }

    out: list[dict[str, Any]] = []
    for agent in agents:
        assert agent is not None
        aid = agent["agent_id"]
        out.append(
            {
                **agent,
                "health": {
                    "sessions_24h": sessions_24h.get(aid, 0),
                    "threats_24h": threats_24h.get(aid, 0),
                    "blocked_24h": blocked_24h.get(aid, 0),
                    "cost_24h_usd": round(cost_24h.get(aid, 0.0), 6),
                    "anomalies_24h": anomalies_24h.get(aid, 0),
                    "active_signals": active_signals.get(aid, 0),
                },
            }
        )
    return out


# ---------------------------------------------------------------- sessions


def get_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    return row_to_dict(row, json_fields=["outcome", "usage", "transcript"])


def upsert_session(conn: sqlite3.Connection, fields: dict[str, Any]) -> dict[str, Any]:
    session_id = fields["session_id"]
    values = (
        fields["agent_id"],
        fields.get("scenario"),
        fields.get("goal"),
        fields.get("system_prompt_ref"),
        fields.get("model"),
        fields.get("temperature"),
        fields.get("status") or "running",
        dumps(fields.get("outcome")),
        dumps(fields.get("usage")),
        fields.get("trace_id"),
        dumps(fields.get("transcript")),
        fields.get("started_at") or now_ms(),
        fields.get("ended_at"),
    )
    existing = conn.execute(
        "SELECT session_id FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE sessions SET agent_id=?, scenario=?, goal=?, system_prompt_ref=?, model=?,
               temperature=?, status=?, outcome=?, usage=?, trace_id=?,
               transcript=COALESCE(?, transcript), started_at=COALESCE(?, started_at), ended_at=?
               WHERE session_id=?""",
            (*values, session_id),
        )
    else:
        conn.execute(
            """INSERT INTO sessions
               (agent_id, scenario, goal, system_prompt_ref, model, temperature,
                status, outcome, usage, trace_id, transcript, started_at, ended_at, session_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (*values, session_id),
        )
    conn.commit()
    session = get_session(conn, session_id)
    assert session is not None
    return session


def _session_filters(
    *,
    scenario: str | None = None,
    agent_id: str | None = None,
    model: str | None = None,
) -> tuple[str, list[Any]]:
    q = ""
    params: list[Any] = []
    if scenario:
        q += " AND scenario = ?"
        params.append(scenario)
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    if model:
        q += " AND model = ?"
        params.append(model)
    return q, params


def count_sessions(
    conn: sqlite3.Connection,
    *,
    scenario: str | None = None,
    agent_id: str | None = None,
    model: str | None = None,
) -> int:
    where, params = _session_filters(scenario=scenario, agent_id=agent_id, model=model)
    row = conn.execute(f"SELECT COUNT(*) FROM sessions WHERE 1=1{where}", params).fetchone()
    return int(row[0] if row else 0)


def list_sessions(
    conn: sqlite3.Connection,
    *,
    scenario: str | None = None,
    agent_id: str | None = None,
    model: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Index rows for pickers/lists — transcripts excluded by design (they're big)."""
    where, params = _session_filters(scenario=scenario, agent_id=agent_id, model=model)
    q = (
        "SELECT session_id, agent_id, scenario, goal, model, status, outcome, usage, trace_id, "
        "started_at, ended_at, (transcript IS NOT NULL) AS has_transcript FROM sessions WHERE 1=1"
        f"{where} ORDER BY started_at DESC, session_id DESC LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])
    rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r, json_fields=["outcome", "usage"]) for r in rows]  # type: ignore[misc]


def list_agent_models(conn: sqlite3.Connection, agent_id: str) -> list[dict[str, Any]]:
    """Distinct models for an agent — cascade picker (docs/12 additive)."""
    rows = conn.execute(
        """SELECT model,
                  COUNT(*) AS session_count,
                  MAX(started_at) AS latest_started_at
           FROM sessions
           WHERE agent_id=? AND model IS NOT NULL AND TRIM(model) != ''
           GROUP BY model
           ORDER BY latest_started_at DESC, model ASC""",
        (agent_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "model": row[0],
                "session_count": int(row[1] or 0),
                "latest_started_at": row[2],
            }
        )
    return out


def session_or_agent_exists(conn: sqlite3.Connection, ref_id: str) -> bool:
    return bool(
        conn.execute("SELECT 1 FROM agents WHERE agent_id=?", (ref_id,)).fetchone()
        or conn.execute("SELECT 1 FROM sessions WHERE session_id=?", (ref_id,)).fetchone()
    )


# ---------------------------------------------------------------- threats


def insert_threat(conn: sqlite3.Connection, threat_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    conn.execute(
        """INSERT INTO threats
           (threat_id, session_id, agent_id, checkpoint, action, category, subcategory,
            risk_score, trust_level, evidence, trace_id, span_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            threat_id,
            fields.get("session_id"),
            fields.get("agent_id"),
            fields.get("checkpoint"),
            fields.get("action"),
            fields.get("category"),
            fields.get("subcategory"),
            fields.get("risk_score"),
            fields.get("trust_level"),
            fields.get("evidence"),
            fields.get("trace_id"),
            fields.get("span_id"),
            now_ms(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM threats WHERE threat_id=?", (threat_id,)).fetchone()
    d = row_to_dict(row)
    assert d is not None
    return d


def count_threats(
    conn: sqlite3.Connection,
    *,
    since: int | None = None,
    agent_id: str | None = None,
) -> int:
    q = "SELECT COUNT(*) FROM threats WHERE 1=1"
    params: list[Any] = []
    if since is not None:
        q += " AND created_at >= ?"
        params.append(since)
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    row = conn.execute(q, params).fetchone()
    return int(row[0] if row else 0)


def list_threats(
    conn: sqlite3.Connection,
    *,
    since: int | None = None,
    agent_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    q = "SELECT * FROM threats WHERE 1=1"
    params: list[Any] = []
    if since is not None:
        q += " AND created_at >= ?"
        params.append(since)
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    q += " ORDER BY created_at DESC, threat_id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def threats_for_session(conn: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM threats WHERE session_id=? ORDER BY created_at ASC, threat_id ASC",
        (session_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


# ---------------------------------------------------------------- sources


def insert_source(conn: sqlite3.Connection, source_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    conn.execute(
        """INSERT INTO sources
           (source_id, session_id, agent_id, origin, trust_level, scan_action, findings, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            source_id,
            fields.get("session_id"),
            fields.get("agent_id"),
            fields.get("origin"),
            fields.get("trust_level"),
            fields.get("scan_action"),
            fields.get("findings") or 0,
            now_ms(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
    d = row_to_dict(row)
    assert d is not None
    return d


def count_sources(
    conn: sqlite3.Connection,
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
) -> int:
    q = "SELECT COUNT(*) FROM sources WHERE 1=1"
    params: list[Any] = []
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    if session_id:
        q += " AND session_id = ?"
        params.append(session_id)
    row = conn.execute(q, params).fetchone()
    return int(row[0] if row else 0)


def list_sources(
    conn: sqlite3.Connection,
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    q = "SELECT * FROM sources WHERE 1=1"
    params: list[Any] = []
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    if session_id:
        q += " AND session_id = ?"
        params.append(session_id)
    q += " ORDER BY created_at DESC, source_id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def sources_for_ref(conn: sqlite3.Connection, ref_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
    """Source ledger by session OR agent id — the agent-view lookup (docs/12)."""
    rows = conn.execute(
        "SELECT * FROM sources WHERE session_id=? OR agent_id=? "
        "ORDER BY created_at DESC, source_id DESC LIMIT ?",
        (ref_id, ref_id, limit),
    ).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


# ---------------------------------------------------------------- signals


def insert_signal(
    conn: sqlite3.Connection,
    signal_id: str,
    fields: dict[str, Any],
    *,
    status: str = "pending",
) -> dict[str, Any]:
    conn.execute(
        """INSERT INTO signals
           (signal_id, session_id, agent_id, kind, severity, reason, evidence_link, guidance, source, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            signal_id,
            fields.get("session_id"),
            fields["agent_id"],
            fields["kind"],
            fields["severity"],
            fields["reason"],
            fields.get("evidence_link"),
            fields.get("guidance"),
            fields.get("source") or "inline",
            status,
            now_ms(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM signals WHERE signal_id=?", (signal_id,)).fetchone()
    d = row_to_dict(row)
    assert d is not None
    return d


def signal_matches_session(signal: dict[str, Any], session_id: str | None) -> bool:
    """One attribution rule for live SSE, reconnect catch-up, and REST.

    A session-scoped subscriber gets its own rows plus agent/fleet-wide rows
    (session_id NULL — e.g. Griffin anomalies, fleet alerts).
    """
    if not session_id:
        return True
    sid = signal.get("session_id")
    return sid is None or sid == session_id


def count_signals(
    conn: sqlite3.Connection,
    *,
    session_id: str | None = None,
    agent_id: str | None = None,
    source: str | None = None,
) -> int:
    q = "SELECT COUNT(*) FROM signals WHERE 1=1"
    params: list[Any] = []
    if session_id:
        q += " AND (session_id = ? OR session_id IS NULL)"
        params.append(session_id)
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    if source:
        q += " AND source = ?"
        params.append(source)
    row = conn.execute(q, params).fetchone()
    return int(row[0] if row else 0)


def list_signals(
    conn: sqlite3.Connection,
    *,
    session_id: str | None = None,
    agent_id: str | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    q = "SELECT * FROM signals WHERE 1=1"
    params: list[Any] = []
    if session_id:
        # Same scoping as signal_matches_session: session rows + fleet-wide rows.
        q += " AND (session_id = ? OR session_id IS NULL)"
        params.append(session_id)
    if agent_id:
        q += " AND agent_id = ?"
        params.append(agent_id)
    if source:
        q += " AND source = ?"
        params.append(source)
    q += " ORDER BY created_at DESC, signal_id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def expire_alert_signals(conn: sqlite3.Connection, agent_id: str, *, window_ms: int) -> None:
    conn.execute(
        """UPDATE signals SET status='expired'
           WHERE agent_id=? AND source='alert' AND status IN ('pending','delivered')
           AND created_at >= ?""",
        (agent_id, now_ms() - window_ms),
    )


# ---------------------------------------------------------------- replays


def insert_replay(conn: sqlite3.Connection, fields: dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO replays
           (replay_id, session_id, candidate_model, candidate_prompt_ref,
            runs, verdict, created_at, duration_ms)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            fields["replay_id"],
            fields["session_id"],
            fields.get("candidate_model"),
            fields.get("candidate_prompt_ref"),
            dumps(fields.get("runs")),
            dumps(fields["verdict"]),
            now_ms(),
            fields.get("duration_ms"),
        ),
    )
    conn.commit()


def get_replay(conn: sqlite3.Connection, replay_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT r.*, s.trace_id
           FROM replays r JOIN sessions s ON s.session_id=r.session_id
           WHERE r.replay_id=?""",
        (replay_id,),
    ).fetchone()
    return row_to_dict(row, json_fields=["verdict", "runs"])


def count_replays(conn: sqlite3.Connection, *, session_id: str | None = None) -> int:
    q = "SELECT COUNT(*) FROM replays WHERE 1=1"
    params: list[Any] = []
    if session_id:
        q += " AND session_id = ?"
        params.append(session_id)
    row = conn.execute(q, params).fetchone()
    return int(row[0] if row else 0)


def list_replays(
    conn: sqlite3.Connection,
    *,
    session_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    q = (
        "SELECT replay_id, session_id, candidate_model, candidate_prompt_ref, verdict, "
        "created_at, duration_ms FROM replays WHERE 1=1"
    )
    params: list[Any] = []
    if session_id:
        q += " AND session_id = ?"
        params.append(session_id)
    q += " ORDER BY created_at DESC, replay_id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r, json_fields=["verdict"]) for r in rows]  # type: ignore[misc]


def latest_replay_for_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT replay_id, verdict FROM replays WHERE session_id=? "
        "ORDER BY created_at DESC, replay_id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    return row_to_dict(row, json_fields=["verdict"])


# ---------------------------------------------------------------- hitl


def insert_hitl(conn: sqlite3.Connection, hitl_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    conn.execute(
        """INSERT INTO hitl_requests (hitl_id, run_id, session_id, payload, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            hitl_id,
            fields["run_id"],
            fields.get("session_id"),
            dumps(fields.get("payload")),
            "pending",
            now_ms(),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM hitl_requests WHERE hitl_id=?", (hitl_id,)).fetchone()
    d = row_to_dict(row, json_fields=["payload"])
    assert d is not None
    return d


def get_hitl(conn: sqlite3.Connection, hitl_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM hitl_requests WHERE hitl_id=?", (hitl_id,)).fetchone()
    return row_to_dict(row, json_fields=["payload"])


def decide_hitl(conn: sqlite3.Connection, hitl_id: str, decision: str) -> dict[str, Any]:
    conn.execute(
        "UPDATE hitl_requests SET status=?, decided_at=? WHERE hitl_id=?",
        (decision, now_ms(), hitl_id),
    )
    conn.commit()
    updated = get_hitl(conn, hitl_id)
    assert updated is not None
    return updated


# ---------------------------------------------------------------- webhooks


def webhook_seen_recently(conn: sqlite3.Connection, fingerprint: str, *, window_ms: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM webhook_events WHERE fingerprint=? AND received_at >= ? LIMIT 1",
        (fingerprint, now_ms() - window_ms),
    ).fetchone()
    return row is not None


def insert_webhook_event(
    conn: sqlite3.Connection, fingerprint: str, status: str, payload: Any
) -> None:
    conn.execute(
        "INSERT INTO webhook_events (fingerprint, status, payload, received_at) VALUES (?,?,?,?)",
        (fingerprint, status, dumps(payload), now_ms()),
    )


# ---------------------------------------------------------------- agent_versions (HQ Agent)


def insert_agent_version(
    conn: sqlite3.Connection,
    version_id: str,
    agent_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    ensure_agent(conn, agent_id, exposure=None, model=fields.get("model"))
    conn.execute(
        """INSERT INTO agent_versions
           (version_id, agent_id, version, model, model_version, source_ref, notes, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            version_id,
            agent_id,
            fields["version"],
            fields.get("model"),
            fields.get("model_version"),
            fields.get("source_ref"),
            fields.get("notes"),
            now_ms(),
        ),
    )
    session_id = fields.get("session_id")
    if session_id:
        pinned = set_session_agent_version(conn, str(session_id), version_id)
        if pinned is None:
            conn.commit()  # version row still persists even if session missing
    else:
        conn.commit()
    row = get_agent_version(conn, version_id)
    assert row is not None
    return row


class ApplyModelError(ValueError):
    """Raised when apply-model cannot complete safely (route maps to 4xx)."""


def apply_agent_model(
    conn: sqlite3.Connection,
    agent_id: str,
    version_id: str,
    *,
    model: str,
    version: str,
    model_version: str | None = None,
    source_ref: str | None = None,
    notes: str | None = None,
    session_id: str | None = None,
    proposal_signal_id: str | None = None,
) -> dict[str, Any]:
    """Human-gated model apply: bump agent.model + register version (+ optional pins).

    Single SQLite transaction — never leaves agents.model changed without a
    matching agent_versions row. Session/proposal refs must belong to agent_id.
    """
    if get_agent_version(conn, version_id) is not None:
        raise ApplyModelError(f"version_id {version_id} already exists")

    if session_id:
        sess = get_session(conn, session_id)
        if sess is None:
            raise ApplyModelError(f"session {session_id} not found")
        if sess.get("agent_id") != agent_id:
            raise ApplyModelError(
                f"session {session_id} belongs to agent {sess.get('agent_id')}, not {agent_id}"
            )

    proposal_row: dict[str, Any] | None = None
    if proposal_signal_id:
        sig = conn.execute(
            "SELECT * FROM signals WHERE signal_id=?", (proposal_signal_id,)
        ).fetchone()
        proposal_row = row_to_dict(sig)
        if proposal_row is None:
            raise ApplyModelError(f"proposal {proposal_signal_id} not found")
        if proposal_row.get("source") != "hq_agent":
            raise ApplyModelError(
                f"proposal {proposal_signal_id} is not source=hq_agent"
            )
        if proposal_row.get("agent_id") != agent_id:
            raise ApplyModelError(
                f"proposal {proposal_signal_id} belongs to agent "
                f"{proposal_row.get('agent_id')}, not {agent_id}"
            )

    try:
        ensure_agent(conn, agent_id, exposure=None, model=model)
        conn.execute(
            "UPDATE agents SET model=?, last_seen=? WHERE agent_id=?",
            (model, now_ms(), agent_id),
        )
        conn.execute(
            """INSERT INTO agent_versions
               (version_id, agent_id, version, model, model_version, source_ref, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                version_id,
                agent_id,
                version,
                model,
                model_version,
                source_ref,
                notes,
                now_ms(),
            ),
        )
        if session_id:
            conn.execute(
                "UPDATE sessions SET agent_version=? WHERE session_id=? AND agent_id=?",
                (version_id, session_id, agent_id),
            )
        if proposal_signal_id:
            cur = conn.execute(
                """UPDATE signals SET status=?
                   WHERE signal_id=? AND source='hq_agent' AND agent_id=?""",
                ("applied", proposal_signal_id, agent_id),
            )
            if cur.rowcount != 1:
                raise ApplyModelError(
                    f"proposal {proposal_signal_id} not updated (wrong agent/source)"
                )
        conn.commit()
    except ApplyModelError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise

    row = get_agent_version(conn, version_id)
    assert row is not None
    proposal: dict[str, Any] | None = None
    if proposal_signal_id:
        sig = conn.execute(
            "SELECT * FROM signals WHERE signal_id=?", (proposal_signal_id,)
        ).fetchone()
        proposal = row_to_dict(sig)
    return {
        "agent_id": agent_id,
        "model": model,
        "version": row,
        "proposal": proposal,
        "applied": True,
    }


def get_agent_version(conn: sqlite3.Connection, version_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM agent_versions WHERE version_id=?", (version_id,)
    ).fetchone()
    return row_to_dict(row)


def list_agent_versions(
    conn: sqlite3.Connection,
    agent_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT * FROM agent_versions WHERE agent_id=?
           ORDER BY created_at DESC, version_id DESC LIMIT ? OFFSET ?""",
        (agent_id, limit, offset),
    ).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def count_agent_versions(conn: sqlite3.Connection, agent_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM agent_versions WHERE agent_id=?", (agent_id,)
    ).fetchone()
    return int(row[0]) if row else 0


def agent_version_timeline(conn: sqlite3.Connection, agent_id: str) -> dict[str, Any]:
    agent = get_agent(conn, agent_id)
    versions = list_agent_versions(conn, agent_id, limit=100, offset=0)
    return {
        "agent_id": agent_id,
        "current_model": (agent or {}).get("model"),
        "versions": versions,
    }
