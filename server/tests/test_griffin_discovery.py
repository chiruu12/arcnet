"""P29 — Griffin metric auto-discovery, eval cap, and top-N ranking."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class GriffinDiscoveryTests(unittest.TestCase):
    def _reset_cache(self) -> None:
        import arcnet_server.griffin as g

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
                "discovery": None,
                "top_series": [],
            }
        )

    def test_discover_includes_new_agent_series(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp_name:
            with patch.dict(
                os.environ,
                {
                    "ARCNET_DB_PATH": str(Path(tmp_name) / "g.db"),
                    "ARCNET_GRIFFIN_SERIES": str(Path(tmp_name) / "griffin_series.json"),
                },
                clear=False,
            ):
                m._conn = None
                self._reset_cache()
                t = 1_700_000_000_000
                conn = m.get_conn()
                for agent_id in ("agent_j", "agent_k"):
                    conn.execute(
                        "INSERT INTO agents(agent_id, name, role, exposure, model, first_seen, last_seen) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (agent_id, agent_id, "ops", "internal", "gpt-4o-mini", t, t),
                    )
                for i in range(35):
                    for agent_id, token_base in (("agent_j", 100), ("agent_k", 500)):
                        usage = json.dumps(
                            {
                                "total_tokens": token_base + i,
                                "cost_usd": 0.01 * i,
                                "tool_calls": i,
                            }
                        )
                        conn.execute(
                            "INSERT INTO sessions(session_id, agent_id, scenario, goal, model, "
                            "temperature, status, outcome, usage, transcript, started_at, ended_at) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                f"s_{agent_id}_{i}",
                                agent_id,
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

                g.run_evaluation_cycle(m.get_conn)
                snap = g.cache_snapshot()
                discovery = snap["discovery"]
                self.assertGreaterEqual(discovery["discovered_count"], 6)
                self.assertIn("arcnet.tokens.total|agent_k", g.active_series())
                self.assertIn("arcnet.tokens.total|agent_k", snap["warmth"])
                m._conn = None

    def test_eval_cap_drops_series_visibly(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp_name:
            with patch.dict(
                os.environ,
                {
                    "ARCNET_DB_PATH": str(Path(tmp_name) / "g.db"),
                    "ARCNET_GRIFFIN_SERIES": str(Path(tmp_name) / "griffin_series.json"),
                    "ARCNET_GRIFFIN_EVAL_CAP": "2",
                },
                clear=False,
            ):
                m._conn = None
                self._reset_cache()
                t = 1_700_000_000_000
                conn = m.get_conn()
                conn.execute(
                    "INSERT INTO agents(agent_id, name, role, exposure, model, first_seen, last_seen) "
                    "VALUES (?,?,?,?,?,?,?)",
                    ("agent_j", "J", "ops", "internal", "gpt-4o-mini", t, t),
                )
                for i in range(35):
                    usage = json.dumps(
                        {"total_tokens": 100 + i, "cost_usd": 0.01 * i, "tool_calls": i}
                    )
                    conn.execute(
                        "INSERT INTO sessions(session_id, agent_id, scenario, goal, model, "
                        "temperature, status, outcome, usage, transcript, started_at, ended_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            f"s_cap_{i}",
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

                g.run_evaluation_cycle(m.get_conn)
                snap = g.cache_snapshot()
                discovery = snap["discovery"]
                self.assertEqual(discovery["eval_cap"], 2)
                self.assertEqual(discovery["evaluated_count"], 2)
                self.assertGreater(discovery["dropped_by_cap"], 0)
                m._conn = None

    def test_top_n_surfaces_highest_z(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp_name:
            series_path = Path(tmp_name) / "griffin_series.json"
            pts = [{"t": float(i), "v": 100.0 + 0.1 * i} for i in range(40)]
            spike_pts = list(pts) + [{"t": 40.0, "v": 10_000.0}]
            data = {
                "arcnet.tokens.total|agent_j": spike_pts,
                "arcnet.cost.usd|agent_j": pts,
                "arcnet.tool.calls|agent_j": pts,
            }
            series_path.write_text(json.dumps(data))
            with patch.dict(
                os.environ,
                {
                    "ARCNET_DB_PATH": str(Path(tmp_name) / "g.db"),
                    "ARCNET_GRIFFIN_SERIES": str(series_path),
                    "ARCNET_GRIFFIN_TOP_N": "2",
                },
                clear=False,
            ):
                m._conn = None
                self._reset_cache()
                g.run_evaluation_cycle(m.get_conn)
                snap = g.cache_snapshot()
                top = snap["top_series"]
                self.assertEqual(len(top), 2)
                self.assertEqual(top[0]["series_id"], "arcnet.tokens.total|agent_j")
                self.assertTrue((top[0].get("z") or 0) > (top[1].get("z") or 0))
                self.assertEqual(snap["discovery"]["top_n"], 2)
                m._conn = None

    def test_default_priorities_order_before_other_agents(self) -> None:
        import arcnet_server.griffin as g

        series = {
            "arcnet.tool.calls|agent_z": [{"t": 1.0, "v": 1.0}],
            "arcnet.tokens.total|agent_j": [{"t": 1.0, "v": 1.0}],
            "arcnet.cost.usd|agent_j": [{"t": 1.0, "v": 1.0}],
        }
        ids = g.discover_series_ids(series)
        self.assertEqual(
            ids[:2],
            ["arcnet.tokens.total|agent_j", "arcnet.cost.usd|agent_j"],
        )
        self.assertIn("arcnet.tool.calls|agent_z", ids)


if __name__ == "__main__":
    unittest.main()
