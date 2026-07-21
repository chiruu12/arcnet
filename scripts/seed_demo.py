#!/usr/bin/env python3
"""Seed demo fleet history in SQLite (Phase 5, docs/03).

Adds the two background agents (Agent L, Agent O) with a day of clean internal
sessions so Fleet Health reads like a fleet, not a single hero agent. All rows
are deterministic (seeded RNG + fixed ids) and idempotent (INSERT OR REPLACE).
Agent J's rows are real scenario recordings — this script never touches them.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BACKGROUND_AGENTS = [
    ("agent_l", "Agent L", "fleet background — kb sync", "internal"),
    ("agent_o", "Agent O", "fleet background — digest", "internal"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo fleet history")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "arcnet.db")
    parser.add_argument("--sessions", type=int, default=9, help="sessions per background agent")
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(args.db))
    rng = random.Random(1997)
    now = int(time.time() * 1000)
    hour = 60 * 60 * 1000

    for agent_id, name, role, exposure in BACKGROUND_AGENTS:
        conn.execute(
            """INSERT OR REPLACE INTO agents
               (agent_id, name, role, exposure, model, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?)""",
            (agent_id, name, role, exposure, "gpt-4o-mini", now - 7 * 24 * hour, now),
        )
        for i in range(args.sessions):
            session_id = f"s_demo_{agent_id}_{i:02d}"
            started = now - rng.randint(1, 23) * hour - rng.randint(0, 3000_000)
            tokens_in = rng.randint(400, 1400)
            tokens_out = rng.randint(80, 400)
            cost = round((tokens_in * 0.15 + tokens_out * 0.60) / 1_000_000, 6)
            usage = {
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "cost_usd": cost,
                "latency_ms": rng.randint(900, 4200),
            }
            outcome = {
                "goal_reached": "clean",
                "exfil_attempts": 0,
                "steps": rng.randint(2, 5),
                "tool_errors": 0,
            }
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, agent_id, scenario, goal, model, temperature, status,
                    outcome, usage, trace_id, transcript, started_at, ended_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    agent_id,
                    None,
                    "background task (demo seed)",
                    "gpt-4o-mini",
                    0.0,
                    "completed",
                    json.dumps(outcome),
                    json.dumps(usage),
                    None,
                    None,  # no transcript: replay honestly refuses demo-seeded sessions
                    started,
                    started + usage["latency_ms"],
                ),
            )

    conn.commit()
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("agents", "sessions")
    }
    print(f"seeded demo fleet into {args.db} — {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
