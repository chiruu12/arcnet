"""Phase 3 — Griffin cold-path soak regression (no seed write)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class GriffinColdSoakTests(unittest.TestCase):
    def test_soak_script_passes_without_seed(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{ROOT / 'sdk'}:{ROOT / 'server'}"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "griffin_cold_soak.py"),
                "--cycles",
                "5",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        self.assertIn("PASS", proc.stdout)

    def test_multi_cycle_proxy_never_writes_seed(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        series_path = Path(tmp.name) / "griffin_series.json"
        os.environ["ARCNET_DB_PATH"] = str(Path(tmp.name) / "g.db")
        os.environ["ARCNET_GRIFFIN_SERIES"] = str(series_path)
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
        t = 1_700_000_000_000
        conn = m.get_conn()
        conn.execute(
            "INSERT INTO agents(agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "J", "ops", "forward_facing", "gpt-4o-mini", t, t),
        )
        for i in range(35):
            usage = json.dumps(
                {"total_tokens": 100 + i, "cost_usd": 0.01 * i, "tool_calls": i}
            )
            conn.execute(
                "INSERT INTO sessions(session_id, agent_id, scenario, goal, model, temperature, "
                "status, outcome, usage, transcript, started_at, ended_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"s_p3_{i}",
                    "agent_j",
                    "S1",
                    "g",
                    "gpt-4o-mini",
                    0.0,
                    "completed",
                    "{}",
                    usage,
                    "{}",
                    t + i * 1000,
                    t + i * 1000,
                ),
            )
        conn.commit()

        statuses = []
        for _ in range(5):
            src = g.ensure_series_warm(m.get_conn)
            self.assertEqual(src, "sqlite_proxy")
            for sid in g.ALLOWLIST:
                if sid in g.active_series():
                    g.evaluate_series(m.get_conn, series_id=sid, observed=None)
            statuses.append(g.cache_snapshot()["status"])

        self.assertFalse(series_path.exists())
        self.assertFalse(all(s == "cold" for s in statuses))
        self.assertNotEqual(g.cache_snapshot()["status"], "cold")
        self.assertEqual(g.cache_snapshot()["series_source"], "sqlite_proxy")


if __name__ == "__main__":
    unittest.main()
