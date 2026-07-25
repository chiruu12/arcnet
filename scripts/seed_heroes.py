#!/usr/bin/env python3
"""Load committed hero incidents from fixtures/heroes.json (idempotent)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "scripts"))

from arcnet_server.db import connect, default_db_path, init_db  # noqa: E402

from hero_fixture import DEFAULT_FIXTURE_PATH, load_fixture, seed_fixture  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed hero sessions from JSON fixture")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: ARCNET_DB_PATH or data/arcnet.db)",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="Hero fixture path (default: fixtures/heroes.json)",
    )
    args = parser.parse_args()

    if not args.fixture.is_file():
        print(f"error: fixture not found: {args.fixture}", file=sys.stderr)
        return 1

    db_path = args.db or default_db_path()
    conn = connect(db_path)
    init_db(conn)
    fixture = load_fixture(args.fixture)
    counts = seed_fixture(conn, fixture)
    print(f"seeded heroes into {db_path} — {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
