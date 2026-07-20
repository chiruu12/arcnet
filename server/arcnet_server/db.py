"""SQLite schema — frozen contract docs/12-data-api.md."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

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
"""


def default_db_path() -> Path:
    env = os.getenv("ARCNET_DB_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data" / "arcnet.db"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
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
