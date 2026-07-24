"""SQLite schema — frozen contract docs/12-data-api.md."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

# Serialize use of a shared connection object (sqlite3 connections are not thread-safe).
_DB_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  agent_id    TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  role        TEXT,
  exposure    TEXT NOT NULL DEFAULT 'internal',
  model       TEXT,
  first_seen  INTEGER,
  last_seen   INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id        TEXT PRIMARY KEY,
  agent_id          TEXT NOT NULL REFERENCES agents(agent_id),
  scenario          TEXT,
  goal              TEXT,
  system_prompt_ref TEXT,
  model             TEXT,
  temperature       REAL,
  status            TEXT NOT NULL,
  outcome           TEXT,
  usage             TEXT,
  trace_id          TEXT,
  transcript        TEXT,
  agent_version     TEXT,
  started_at        INTEGER,
  ended_at          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id, started_at);

CREATE TABLE IF NOT EXISTS signals (
  signal_id    TEXT PRIMARY KEY,
  session_id   TEXT,
  agent_id     TEXT NOT NULL,
  kind         TEXT NOT NULL,
  severity     TEXT NOT NULL,
  reason       TEXT NOT NULL,
  evidence_link TEXT,
  guidance     TEXT,
  source       TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending',
  created_at   INTEGER,
  delivered_at INTEGER
);

CREATE TABLE IF NOT EXISTS threats (
  threat_id   TEXT PRIMARY KEY,
  session_id  TEXT,
  agent_id    TEXT,
  checkpoint  TEXT,
  action      TEXT,
  category    TEXT,
  subcategory TEXT,
  risk_score  REAL,
  trust_level TEXT,
  evidence    TEXT,
  trace_id    TEXT,
  span_id     TEXT,
  created_at  INTEGER
);

CREATE TABLE IF NOT EXISTS sources (
  source_id   TEXT PRIMARY KEY,
  session_id  TEXT,
  agent_id    TEXT,
  origin      TEXT,
  trust_level TEXT,
  scan_action TEXT,
  findings    INTEGER DEFAULT 0,
  created_at  INTEGER
);

CREATE TABLE IF NOT EXISTS replays (
  replay_id            TEXT PRIMARY KEY,
  session_id           TEXT NOT NULL REFERENCES sessions(session_id),
  candidate_model      TEXT,
  candidate_prompt_ref TEXT,
  runs                 TEXT,
  verdict              TEXT NOT NULL,
  created_at           INTEGER,
  duration_ms          INTEGER
);

CREATE TABLE IF NOT EXISTS hitl_requests (
  hitl_id     TEXT PRIMARY KEY,
  run_id      TEXT NOT NULL,
  session_id  TEXT,
  payload     TEXT,
  status      TEXT NOT NULL DEFAULT 'pending',
  created_at  INTEGER,
  decided_at  INTEGER
);

CREATE TABLE IF NOT EXISTS webhook_events (
  fingerprint TEXT,
  status      TEXT,
  payload     TEXT,
  received_at INTEGER,
  PRIMARY KEY (fingerprint, received_at)
);

CREATE TABLE IF NOT EXISTS agent_versions (
  version_id     TEXT PRIMARY KEY,
  agent_id       TEXT NOT NULL REFERENCES agents(agent_id),
  version        TEXT NOT NULL,
  model          TEXT,
  model_version  TEXT,
  source_ref     TEXT,
  notes          TEXT,
  created_at     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_agent_versions_agent ON agent_versions(agent_id, created_at DESC);
"""


def default_db_path() -> Path:
    env = os.getenv("ARCNET_DB_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data" / "arcnet.db"


class _LockedResultCursor:
    """Keeps the DB lock until the SELECT cursor is drained."""

    __slots__ = ("_lock", "_cursor", "_released")

    def __init__(self, lock: threading.RLock, cursor: sqlite3.Cursor) -> None:
        self._lock = lock
        self._cursor = cursor
        self._released = False

    def _release(self) -> None:
        if not self._released:
            self._released = True
            self._lock.release()

    def fetchone(self) -> sqlite3.Row | None:
        try:
            return self._cursor.fetchone()
        finally:
            self._release()

    def fetchall(self) -> list[sqlite3.Row]:
        try:
            return self._cursor.fetchall()
        finally:
            self._release()

    def __iter__(self) -> Any:
        try:
            return iter(self._cursor.fetchall())
        finally:
            self._release()


class _ThreadSafeConnection:
    """Proxy that serializes access to one sqlite3 connection across threads."""

    __slots__ = ("_conn",)

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, *args: Any, **kwargs: Any) -> sqlite3.Cursor:
        _DB_LOCK.acquire()
        try:
            cur = self._conn.execute(*args, **kwargs)
            if cur.description is None:
                _DB_LOCK.release()
                return cur
            return _LockedResultCursor(_DB_LOCK, cur)  # type: ignore[return-value]
        except Exception:
            _DB_LOCK.release()
            raise

    def executemany(self, *args: Any, **kwargs: Any) -> sqlite3.Cursor:
        with _DB_LOCK:
            return self._conn.executemany(*args, **kwargs)

    def executescript(self, script: str) -> sqlite3.Cursor:
        with _DB_LOCK:
            return self._conn.executescript(script)

    def commit(self) -> None:
        with _DB_LOCK:
            self._conn.commit()

    def rollback(self) -> None:
        with _DB_LOCK:
            self._conn.rollback()

    def close(self) -> None:
        with _DB_LOCK:
            self._conn.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(str(path), check_same_thread=False)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA journal_mode=WAL;")
    raw.execute("PRAGMA busy_timeout=5000;")
    raw.execute("PRAGMA foreign_keys=ON;")
    return _ThreadSafeConnection(raw)  # type: ignore[return-value]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """Additive column for existing DBs (docs/12 — no migration tool in v1)."""
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_column(conn, "sessions", "agent_version", "TEXT")
    _ensure_column(conn, "threats", "findings_detail", "TEXT")
    _ensure_column(conn, "threats", "pattern_class", "TEXT")
    _ensure_column(conn, "threats", "guard_verdict", "TEXT")
    _ensure_column(conn, "sources", "findings_detail", "TEXT")
    _ensure_column(conn, "sources", "guard_verdict", "TEXT")
    _ensure_column(conn, "signals", "guard_verdict", "TEXT")
    conn.commit()


def row_to_dict(row: sqlite3.Row | None, *, json_fields: list[str] | None = None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for k in json_fields or []:
        if d.get(k) is not None and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


def now_ms() -> int:
    return int(time.time() * 1000)


def dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    return json.dumps(obj)
