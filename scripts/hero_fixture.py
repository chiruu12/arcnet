"""Hero incident fixture — export from maintainer DB, seed into cold clones.

Exports the two recorded demo sessions (Edgar S1, Worms S4) and every related
row discoverable from the schema (tables with session_id, plus agents and
agent_versions referenced by those sessions). Deterministic JSON for clean diffs.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_PATH = ROOT / "fixtures" / "heroes.json"

# Recorded heroes referenced across HQ, docs, and phase4_g4_check.
DEFAULT_SESSION_IDS = ("s_ecfdb55d", "s_2af44726")

FIXTURE_VERSION = 1

# FK-safe insert order (discovered tables not listed here append after sessions).
TABLE_INSERT_ORDER = (
    "agents",
    "agent_versions",
    "sessions",
    "threats",
    "sources",
    "signals",
    "replays",
    "hitl_requests",
    "webhook_events",
)


def _table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _primary_key_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall() if c[5]]


def _session_scoped_tables(conn: sqlite3.Connection) -> list[str]:
    return [t for t in _table_names(conn) if "session_id" in _table_columns(conn, t)]


def _hero_agent_ids(conn: sqlite3.Connection, session_ids: tuple[str, ...]) -> list[str]:
    placeholders = ",".join("?" * len(session_ids))
    rows = conn.execute(
        f"SELECT DISTINCT agent_id FROM sessions WHERE session_id IN ({placeholders})",
        session_ids,
    ).fetchall()
    return sorted(r[0] for r in rows)


def _hero_version_ids(conn: sqlite3.Connection, session_ids: tuple[str, ...]) -> list[str]:
    placeholders = ",".join("?" * len(session_ids))
    rows = conn.execute(
        f"""SELECT DISTINCT agent_version FROM sessions
            WHERE session_id IN ({placeholders}) AND agent_version IS NOT NULL
              AND TRIM(agent_version) != ''""",
        session_ids,
    ).fetchall()
    return sorted(r[0] for r in rows)


def _row_dict(row: sqlite3.Row, columns: list[str]) -> dict[str, Any]:
    return {col: row[idx] for idx, col in enumerate(columns)}


def _sort_rows(rows: list[dict[str, Any]], pk_cols: list[str]) -> list[dict[str, Any]]:
    if not pk_cols:
        return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))
    return sorted(rows, key=lambda r: tuple(r.get(c) for c in pk_cols))


def _fetch_table_rows(
    conn: sqlite3.Connection,
    table: str,
    session_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    columns = _table_columns(conn, table)
    pk_cols = _primary_key_columns(conn, table)
    placeholders = ",".join("?" * len(session_ids))

    if "session_id" in columns:
        sql = f"SELECT * FROM {table} WHERE session_id IN ({placeholders})"
        params: tuple[Any, ...] = session_ids
    elif table == "agents":
        agent_ids = _hero_agent_ids(conn, session_ids)
        if not agent_ids:
            return []
        ap = ",".join("?" * len(agent_ids))
        sql = f"SELECT * FROM {table} WHERE agent_id IN ({ap})"
        params = tuple(agent_ids)
    elif table == "agent_versions":
        agent_ids = _hero_agent_ids(conn, session_ids)
        version_ids = _hero_version_ids(conn, session_ids)
        clauses: list[str] = []
        params_list: list[Any] = []
        if agent_ids:
            ap = ",".join("?" * len(agent_ids))
            clauses.append(f"agent_id IN ({ap})")
            params_list.extend(agent_ids)
        if version_ids:
            vp = ",".join("?" * len(version_ids))
            clauses.append(f"version_id IN ({vp})")
            params_list.extend(version_ids)
        if not clauses:
            return []
        sql = f"SELECT * FROM {table} WHERE {' OR '.join(clauses)}"
        params = tuple(params_list)
    else:
        return []

    rows = conn.execute(sql, params).fetchall()
    out = [_row_dict(r, columns) for r in rows]
    return _sort_rows(out, pk_cols)


def export_fixture(conn: sqlite3.Connection, session_ids: tuple[str, ...]) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in _table_names(conn):
        rows = _fetch_table_rows(conn, table, session_ids)
        if rows:
            tables[table] = rows
    return {
        "version": FIXTURE_VERSION,
        "session_ids": list(session_ids),
        "tables": tables,
    }


def _ordered_table_names(tables: dict[str, list[dict[str, Any]]]) -> list[str]:
    known = [t for t in TABLE_INSERT_ORDER if t in tables]
    rest = sorted(t for t in tables if t not in TABLE_INSERT_ORDER)
    return known + rest


def seed_fixture(conn: sqlite3.Connection, fixture: dict[str, Any]) -> dict[str, int]:
    tables: dict[str, list[dict[str, Any]]] = fixture.get("tables") or {}
    counts: dict[str, int] = {}
    for table in _ordered_table_names(tables):
        rows = tables[table]
        if not rows:
            counts[table] = 0
            continue
        columns = list(rows[0].keys())
        # Hero fixture must not clobber seeded agent_versions.model — skip that table.
        if table == "agent_versions":
            counts[table] = 0
            continue
        col_list = ", ".join(columns)
        placeholders = ", ".join("?" * len(columns))
        sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
        for row in rows:
            conn.execute(sql, tuple(row[c] for c in columns))
        counts[table] = len(rows)
    conn.commit()
    return counts


def write_fixture(path: Path, fixture: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
