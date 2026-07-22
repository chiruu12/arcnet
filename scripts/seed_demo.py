#!/usr/bin/env python3
"""Seed demo fleet history in SQLite (Phase 5, docs/03).

Adds the two background agents (Agent L, Agent O) with a day of clean internal
sessions so Fleet Health reads like a fleet, not a single hero agent. Registers
baseline agent_versions (with honest source_ref placeholders) so HQ version-first
cascade has something to pick. All rows are deterministic (seeded RNG + fixed ids)
and idempotent (INSERT OR REPLACE). Agent J's scenario recordings are not rewritten;
a baseline version row is registered if agent_j already exists.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from arcnet_server.db import connect, default_db_path, init_db  # noqa: E402

BACKGROUND_AGENTS = [
    ("agent_l", "Agent L", "fleet background — kb sync", "internal"),
    ("agent_o", "Agent O", "fleet background — digest", "internal"),
]

# Deterministic baseline versions for cascade pickers (Wave A / WS4).
BASELINE_VERSIONS = [
    ("agent_l", "av_demo_agent_l", "demo.baseline", "gpt-4o-mini", "agents/prompts/agent_l.md"),
    ("agent_o", "av_demo_agent_o", "demo.baseline", "gpt-4o-mini", "agents/prompts/agent_o.md"),
    ("agent_j", "av_demo_agent_j", "demo.baseline", "gpt-4o-mini", "agents/prompts/agent_j.md"),
]


def _ensure_baseline_version(
    conn,
    *,
    agent_id: str,
    version_id: str,
    version: str,
    model: str,
    source_ref: str,
    created_at: int,
) -> None:
    agent = conn.execute(
        "SELECT agent_id, model FROM agents WHERE agent_id=?", (agent_id,)
    ).fetchone()
    if agent is None:
        return
    existing = conn.execute(
        "SELECT version_id FROM agent_versions WHERE version_id=?", (version_id,)
    ).fetchone()
    if existing:
        return
    fleet_model = agent[1] or model
    conn.execute(
        """INSERT INTO agent_versions
           (version_id, agent_id, version, model, model_version, source_ref, notes, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            version_id,
            agent_id,
            version,
            fleet_model,
            None,
            source_ref,
            "seed_demo baseline — placeholder source_ref",
            created_at,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo fleet history")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: ARCNET_DB_PATH or data/arcnet.db)",
    )
    parser.add_argument("--sessions", type=int, default=9, help="sessions per background agent")
    args = parser.parse_args()

    db_path = args.db or default_db_path()
    conn = connect(db_path)
    init_db(conn)
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
            # Pin first session of each background agent to baseline version_id.
            pin = f"av_demo_{agent_id}" if i == 0 else None
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, agent_id, scenario, goal, model, temperature, status,
                    outcome, usage, trace_id, transcript, agent_version, started_at, ended_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                    pin,
                    started,
                    started + usage["latency_ms"],
                ),
            )

    for agent_id, version_id, version, model, source_ref in BASELINE_VERSIONS:
        _ensure_baseline_version(
            conn,
            agent_id=agent_id,
            version_id=version_id,
            version=version,
            model=model,
            source_ref=source_ref,
            created_at=now - 24 * hour,
        )

    conn.commit()
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("agents", "sessions", "agent_versions")
    }
    print(f"seeded demo fleet into {db_path} — {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
