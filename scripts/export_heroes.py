#!/usr/bin/env python3
"""Export hero incident rows from the maintainer DB into fixtures/heroes.json.

Read-only against the source database. Run on the machine that holds the
recorded Edgar (S1) and Worms (S4) sessions before committing the fixture.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "scripts"))

from arcnet_server.db import connect, default_db_path  # noqa: E402

from hero_fixture import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
    DEFAULT_SESSION_IDS,
    export_fixture,
    write_fixture,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export hero sessions to JSON fixture")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: ARCNET_DB_PATH or data/arcnet.db)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="Output fixture path (default: fixtures/heroes.json)",
    )
    parser.add_argument(
        "--session",
        action="append",
        dest="sessions",
        help="Session id to export (default: both hero sessions)",
    )
    args = parser.parse_args()

    db_path = args.db or default_db_path()
    if not db_path.is_file():
        print(f"error: database not found: {db_path}", file=sys.stderr)
        return 1

    session_ids = tuple(args.sessions) if args.sessions else DEFAULT_SESSION_IDS
    conn = connect(db_path)
    fixture = export_fixture(conn, session_ids)
    write_fixture(args.out, fixture)

    counts = {table: len(rows) for table, rows in fixture["tables"].items()}
    print(f"exported heroes from {db_path} -> {args.out}")
    for table in sorted(counts):
        print(f"  {table}: {counts[table]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
