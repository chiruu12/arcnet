#!/usr/bin/env python3
"""Phase 3 — Griffin cold-path soak (no seed file).

Runs N warm/evaluate cycles against SQLite usage only. Asserts:
  - no griffin_series.json seed write
  - series_source stays sqlite_proxy (or honest none if DB empty)
  - status is not stuck at cold once proxy series exist

  PYTHONPATH=sdk:server uv run python scripts/griffin_cold_soak.py
  PYTHONPATH=sdk:server uv run python scripts/griffin_cold_soak.py --cycles 8
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fail(msg: str) -> int:
    print(f"griffin cold soak FAIL: {msg}", file=sys.stderr)
    return 1


def _seed_usage_sessions(conn, *, n: int = 40) -> None:
    t = int(time.time() * 1000) - n * 60_000
    conn.execute(
        "INSERT OR IGNORE INTO agents(agent_id, name, role, exposure, model, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?)",
        ("agent_j", "J", "ops", "forward_facing", "gpt-4o-mini", t, t),
    )
    for i in range(n):
        usage = json.dumps(
            {
                "total_tokens": 80 + i * 3,
                "cost_usd": 0.001 * (i + 1),
                "tool_calls": i % 7,
            }
        )
        conn.execute(
            "INSERT INTO sessions(session_id, agent_id, scenario, goal, model, temperature, "
            "status, outcome, usage, transcript, started_at, ended_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"s_soak_{i}",
                "agent_j",
                "S1",
                "soak",
                "gpt-4o-mini",
                0.0,
                "completed",
                "{}",
                usage,
                "{}",
                t + i * 60_000,
                t + i * 60_000,
            ),
        )
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=5, help="warm/evaluate cycles (default 5)")
    args = parser.parse_args()
    n = max(1, args.cycles)

    sys.path.insert(0, str(ROOT / "sdk"))
    sys.path.insert(0, str(ROOT / "server"))

    with tempfile.TemporaryDirectory(prefix="arcnet_griffin_soak_") as tmp_name:
        tmp = Path(tmp_name)
        db_path = tmp / "soak.db"
        series_path = tmp / "griffin_series.json"
        os.environ["ARCNET_DB_PATH"] = str(db_path)
        os.environ["ARCNET_GRIFFIN_SERIES"] = str(series_path)

        import arcnet_server.griffin as g
        import arcnet_server.main as m

        m._conn = None
        g._CACHE.update(
            {
                "model": "mad",
                "estimator": "mad",
                "status": "cold",
                "series": {},
                "proxy_series": {},
                "series_source": None,
                "last_cycle_ms": None,
                "last_evaluate_ms": None,
                "last_anomaly": None,
                "anomalies": [],
            }
        )

        conn = m.get_conn()
        _seed_usage_sessions(conn)

        sources: list[str] = []
        statuses: list[str] = []
        for i in range(n):
            # Mimic loop: warm then evaluate allowlist series present in proxy
            src = g.ensure_series_warm(m.get_conn)
            sources.append(src)
            series = g.active_series()
            for sid in g.ALLOWLIST:
                if sid in series:
                    g.evaluate_series(m.get_conn, series_id=sid, observed=None)
            snap = g.cache_snapshot()
            statuses.append(str(snap.get("status") or "cold"))
            print(
                f"cycle {i + 1}/{n}: source={src} status={snap.get('status')} "
                f"series_count={snap.get('series_count')} seed_exists={series_path.exists()}"
            )

        if series_path.exists():
            return _fail("seed file was written during cold-path soak")

        if any(s != "sqlite_proxy" for s in sources):
            return _fail(f"expected series_source=sqlite_proxy every cycle, got {sources}")

        if all(s == "cold" for s in statuses):
            return _fail(f"status stuck cold across {n} cycles: {statuses}")

        final = g.cache_snapshot()
        if final.get("series_source") != "sqlite_proxy":
            return _fail(f"final series_source={final.get('series_source')!r}")
        if final.get("status") == "cold":
            return _fail("final status still cold with proxy series present")

        print(
            f"griffin cold soak PASS: cycles={n} source=sqlite_proxy "
            f"status={final.get('status')} no_seed=True"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
