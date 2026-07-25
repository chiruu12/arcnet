#!/usr/bin/env python3
"""Conservative hygiene for the demo SQLite database.

Removes test-origin telemetry that leaked into data/arcnet.db before suite
guards landed. Defaults to dry-run; --apply copies a timestamped backup first.

Criteria (documented in docs/32-deployment-notes.md):
  1. Orphan child rows — session_id set but no matching sessions row.
  2. Known test session trees — explicit session_id literals from test suites.
Hero sessions s_ecfdb55d and s_2af44726 are hard-protected. s_demo_* seed rows
are never removed.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from arcnet_server.db import connect, default_db_path, init_db  # noqa: E402

PROTECTED_SESSION_IDS = frozenset({"s_ecfdb55d", "s_2af44726"})

# One definition of "orphan", shared by the preview, the counts, and the DELETE.
# These must never drift apart: a dry run that does not predict what --apply does
# is worse than no dry run at all. Rows recorded during a replay carry the
# replay_id in session_id and have no `sessions` row by design — they are real
# provenance, not orphans.
ORPHAN_PREDICATE = """session_id IS NOT NULL
              AND session_id NOT IN (SELECT session_id FROM sessions)
              AND session_id NOT IN (SELECT replay_id FROM replays)"""

# Explicit session_id literals from test modules (never heuristic guesses).
KNOWN_TEST_SESSION_IDS = frozenset(
    {
        "s_bad",
        "s_canary",
        "s_case",
        "s_c1",
        "s_coherence",
        "s_ev_1",
        "s_fx_1",
        "s_hard",
        "s_hitl_relay",
        "s_hitl_smoke",
        "s_huge",
        "s_ingest",
        "s_meta",
        "s_nope",
        "s_one",
        "s_other",
        "s_page",
        "s_page_a",
        "s_page_c",
        "s_pin_a",
        "s_pin_b",
        "s_replay_cc",
        "s_replay_steer",
        "s_rm",
        "s_robust",
        "s_rt",
        "s_sdk",
        "s_test",
        "s_threat",
        "s_w",
        "s_wa",
        "s_x",
    }
)

SESSION_SCOPED_TABLES = (
    "threats",
    "sources",
    "signals",
    "replays",
    "hitl_requests",
)

COUNT_TABLES = (
    "agents",
    "sessions",
    "threats",
    "sources",
    "signals",
    "replays",
    "hitl_requests",
    "agent_versions",
    "webhook_events",
)

HERO_CHILD_TABLES = ("threats", "sources", "signals", "replays")


@dataclass
class RemovalPlan:
    sessions: list[str] = field(default_factory=list)
    orphans_by_table: dict[str, list[str]] = field(default_factory=dict)
    session_children_by_table: dict[str, list[str]] = field(default_factory=dict)

    def orphan_session_ids(self) -> set[str]:
        ids: set[str] = set()
        for sids in self.orphans_by_table.values():
            ids.update(sids)
        return ids

    def all_affected_session_ids(self) -> set[str]:
        ids = set(self.sessions)
        ids.update(self.orphan_session_ids())
        for sids in self.session_children_by_table.values():
            ids.update(sids)
        return ids


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _existing_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def _is_demo_seed_session(session_id: str) -> bool:
    return session_id.startswith("s_demo_")


def _assert_heroes_safe(plan: RemovalPlan) -> None:
    affected = plan.all_affected_session_ids()
    for hero in PROTECTED_SESSION_IDS:
        if hero in affected:
            raise RuntimeError(
                f"refusing to proceed: hero session {hero} would be removed"
            )
        if hero in plan.sessions:
            raise RuntimeError(
                f"refusing to proceed: hero session {hero} matched session removal"
            )
    for hero in PROTECTED_SESSION_IDS:
        if hero in KNOWN_TEST_SESSION_IDS:
            raise RuntimeError(f"configuration error: hero {hero} in KNOWN_TEST_SESSION_IDS")


def _known_test_sessions(conn: sqlite3.Connection) -> list[str]:
    if not KNOWN_TEST_SESSION_IDS:
        return []
    placeholders = ",".join("?" * len(KNOWN_TEST_SESSION_IDS))
    rows = conn.execute(
        f"""SELECT session_id FROM sessions
            WHERE session_id IN ({placeholders})
            ORDER BY session_id""",
        tuple(sorted(KNOWN_TEST_SESSION_IDS)),
    ).fetchall()
    out = [r[0] for r in rows]
    for sid in out:
        if sid in PROTECTED_SESSION_IDS or _is_demo_seed_session(sid):
            raise RuntimeError(f"refusing to proceed: protected session {sid} in test list")
    return out


def build_plan(conn: sqlite3.Connection) -> RemovalPlan:
    plan = RemovalPlan()
    plan.sessions = _known_test_sessions(conn)

    for table in SESSION_SCOPED_TABLES:
        if table not in _existing_tables(conn):
            continue
        cols = _table_columns(conn, table)
        if "session_id" not in cols:
            continue

        orphan_rows = conn.execute(
            f"""SELECT DISTINCT session_id FROM {table}
                WHERE {ORPHAN_PREDICATE}
                ORDER BY session_id"""
        ).fetchall()
        if orphan_rows:
            plan.orphans_by_table[table] = [r[0] for r in orphan_rows]

        if plan.sessions:
            ph = ",".join("?" * len(plan.sessions))
            child_rows = conn.execute(
                f"""SELECT DISTINCT session_id FROM {table}
                    WHERE session_id IN ({ph})
                    ORDER BY session_id""",
                tuple(plan.sessions),
            ).fetchall()
            if child_rows:
                plan.session_children_by_table[table] = [r[0] for r in child_rows]

    _assert_heroes_safe(plan)
    return plan


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in COUNT_TABLES:
        if table in _existing_tables(conn):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def _count_rows_for_sessions(
    conn: sqlite3.Connection, table: str, session_ids: list[str]
) -> int:
    if not session_ids or table not in _existing_tables(conn):
        return 0
    ph = ",".join("?" * len(session_ids))
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE session_id IN ({ph})",
        tuple(session_ids),
    ).fetchone()[0]


def _count_orphan_rows(conn: sqlite3.Connection, table: str) -> int:
    if table not in _existing_tables(conn):
        return 0
    return conn.execute(
        f"""SELECT COUNT(*) FROM {table}
            WHERE {ORPHAN_PREDICATE}"""
    ).fetchone()[0]


def plan_row_counts(conn: sqlite3.Connection, plan: RemovalPlan) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for table in SESSION_SCOPED_TABLES:
        counts[table] += _count_orphan_rows(conn, table)
    for table in SESSION_SCOPED_TABLES:
        counts[table] += _count_rows_for_sessions(conn, table, plan.sessions)
    counts["sessions"] = len(plan.sessions)
    return dict(counts)


def _sample_ids(session_ids: set[str], limit: int = 8) -> list[str]:
    return sorted(session_ids)[:limit]


def print_plan(
    conn: sqlite3.Connection,
    plan: RemovalPlan,
    *,
    heading: str = "DRY RUN",
) -> None:
    print(f"clean_demo_db [{heading}] — {conn.execute('PRAGMA database_list').fetchone()[2]}")
    print()
    print("Removal criteria:")
    print("  • orphan child rows (session_id with no sessions row)")
    print("  • known test session trees (explicit literals from test suites)")
    print(f"  • protected heroes: {', '.join(sorted(PROTECTED_SESSION_IDS))}")
    print("  • seed_demo sessions (s_demo_*) are never removed")
    print()

    row_counts = plan_row_counts(conn, plan)
    total_rows = sum(row_counts.values())
    if total_rows == 0:
        print("Nothing to remove.")
    else:
        print("Would remove:")
        if plan.sessions:
            print(f"  sessions: {len(plan.sessions)} row(s)")
            print(f"    sample session_ids: {_sample_ids(set(plan.sessions))}")
        for table in SESSION_SCOPED_TABLES:
            n_orphan = _count_orphan_rows(conn, table)
            n_sess = _count_rows_for_sessions(conn, table, plan.sessions)
            n = n_orphan + n_sess
            if n == 0:
                continue
            orphan_ids = set(plan.orphans_by_table.get(table, []))
            sess_ids = set(plan.session_children_by_table.get(table, []))
            sample = _sample_ids(orphan_ids | sess_ids)
            print(f"  {table}: {n} row(s)")
            if sample:
                print(f"    sample session_ids: {sample}")

    print()
    before = table_counts(conn)
    print("Table counts (before):")
    for table in COUNT_TABLES:
        if table in before:
            print(f"  {table}: {before[table]}")
    if heading == "DRY RUN":
        after = dict(before)
        for table, n in row_counts.items():
            after[table] = max(0, after.get(table, 0) - n)
        print()
        print("Table counts (projected after):")
        for table in COUNT_TABLES:
            if table in after:
                print(f"  {table}: {after[table]}")


def backup_database(db_path: Path) -> Path:
    """Consistent full copy via the SQLite backup API.

    A plain file copy is NOT safe here: the database runs in WAL mode, so recent
    commits live in the sidecar ``-wal`` file until a checkpoint. Copying only
    ``arcnet.db`` silently drops them — a backup that looks fine and isn't. The
    backup API reads through the WAL and writes one consistent database.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = db_path.with_name(f"{db_path.stem}.backup.{ts}{db_path.suffix}")
    try:
        src = sqlite3.connect(db_path)
        try:
            dest = sqlite3.connect(backup_path)
            try:
                src.backup(dest)
            finally:
                dest.close()
        finally:
            src.close()
    except (OSError, sqlite3.Error) as exc:
        raise RuntimeError(f"backup failed: {exc}") from exc
    if not backup_path.is_file() or backup_path.stat().st_size == 0:
        raise RuntimeError(f"backup missing or empty: {backup_path}")

    # A backup that lost rows is worse than no backup — verify row parity.
    src = sqlite3.connect(db_path)
    dest = sqlite3.connect(backup_path)
    try:
        for table in _existing_tables(src):
            n_src = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            n_dest = dest.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if n_src != n_dest:
                raise RuntimeError(
                    f"backup verification failed on {table}: {n_src} rows in source, "
                    f"{n_dest} in backup"
                )
    finally:
        src.close()
        dest.close()
    return backup_path


def apply_plan(conn: sqlite3.Connection, plan: RemovalPlan) -> None:
    _assert_heroes_safe(plan)
    for table in SESSION_SCOPED_TABLES:
        if table not in _existing_tables(conn):
            continue
        conn.execute(
            f"""DELETE FROM {table}
                WHERE {ORPHAN_PREDICATE}"""
        )
    if plan.sessions:
        ph = ",".join("?" * len(plan.sessions))
        for table in SESSION_SCOPED_TABLES:
            if table not in _existing_tables(conn):
                continue
            conn.execute(
                f"DELETE FROM {table} WHERE session_id IN ({ph})",
                tuple(plan.sessions),
            )
        conn.execute(
            f"DELETE FROM sessions WHERE session_id IN ({ph})",
            tuple(plan.sessions),
        )
    conn.commit()


def hero_snapshot(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    snap: dict[str, dict[str, Any]] = {}
    for hero in sorted(PROTECTED_SESSION_IDS):
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id=?", (hero,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"hero session missing: {hero}")
        child: dict[str, list[dict[str, Any]]] = {}
        for table in HERO_CHILD_TABLES:
            if table not in _existing_tables(conn):
                continue
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE session_id=? ORDER BY rowid",
                (hero,),
            ).fetchall()
            child[table] = [{cols[i]: r[i] for i in range(len(cols))} for r in rows]
        snap[hero] = {
            "session": dict(row),
            "children": child,
        }
    return snap


def assert_heroes_intact(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> None:
    for hero in PROTECTED_SESSION_IDS:
        if hero not in before or hero not in after:
            raise RuntimeError(f"hero {hero} missing from snapshot")
        if before[hero] != after[hero]:
            raise RuntimeError(f"hero session {hero} changed after cleanup")


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean test-origin rows from demo SQLite")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: ARCNET_DB_PATH or data/arcnet.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply removals (default: dry run only)",
    )
    args = parser.parse_args()

    db_path = args.db or default_db_path()
    if not db_path.is_file():
        print(f"error: database not found: {db_path}", file=sys.stderr)
        return 1

    conn = connect(db_path)
    init_db(conn)
    plan = build_plan(conn)

    if not args.apply:
        print_plan(conn, plan, heading="DRY RUN")
        return 0

    before_counts = table_counts(conn)
    hero_before = hero_snapshot(conn)
    print_plan(conn, plan, heading="PRE-APPLY")
    backup_path = backup_database(db_path)
    print(f"backup written: {backup_path}")
    print()

    apply_plan(conn, plan)
    hero_after = hero_snapshot(conn)
    assert_heroes_intact(hero_before, hero_after)

    after_counts = table_counts(conn)
    print()
    print("Table counts (after):")
    for table in COUNT_TABLES:
        if table in after_counts:
            b, a = before_counts.get(table, 0), after_counts[table]
            delta = a - b
            suffix = f" ({delta:+d})" if delta else ""
            print(f"  {table}: {a}{suffix}")
    print()
    print("Hero integrity: OK — both protected sessions unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
