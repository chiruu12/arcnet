"""Robustness pass — version pinpoint, bounded sources, dashboards twin."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class RobustnessPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "robust.db")
        # Force snapshot catalog in recommend tests unless overridden.
        os.environ.pop("OPENAI_API_KEY", None)
        import arcnet_server.main as m
        from arcnet_server.db import now_ms

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app)
        conn = m.get_conn()
        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "Agent J", "support/ops", "forward_facing", "gpt-4o-mini", ts, ts),
        )
        conn.execute(
            """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
               status, outcome, usage, trace_id, transcript, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "s_robust",
                "agent_j",
                "S1",
                "goal",
                "gpt-4o-mini",
                0.0,
                "completed",
                json.dumps({"goal_reached": "exploited"}),
                json.dumps({"cost_usd": 0.01}),
                "trace_robust",
                json.dumps({"steps": [{"i": 0, "type": "model_turn"}], "final_output": "x"}),
                ts,
                ts,
            ),
        )
        conn.execute(
            """INSERT INTO sources (source_id, session_id, agent_id, origin, trust_level,
               scan_action, findings, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                "src_robust",
                "s_robust",
                "agent_j",
                "http://evil.example/payload",
                "retrieved",
                "block",
                json.dumps([{"category": "injection", "evidence": "SECRET " + ("z" * 400)}]),
                ts,
            ),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_check_includes_version_pinpoint(self) -> None:
        applied = self.client.post(
            "/api/agents/agent_j/apply-model",
            json={
                "confirm": True,
                "model": "gpt-4o",
                "version": "robust-1",
                "session_id": "s_robust",
            },
        )
        self.assertEqual(applied.status_code, 200)
        check = self.client.get("/api/agent-view/check/s_robust").json()
        data = check["data"]
        self.assertIn("version_pinpoint", data)
        self.assertIn("narrative", data["version_pinpoint"])
        self.assertIsNotNone(data["session"].get("agent_version"))
        self.assertTrue(data["version_pinpoint"]["pinned_version"])
        self.assertIn("versions", data["related_views"])

    def test_sources_agent_view_is_bounded(self) -> None:
        env = self.client.get("/api/agent-view/sources/s_robust").json()
        self.assertEqual(env["view"], "sources")
        sources = env["data"]["sources"]
        self.assertTrue(sources)
        row = sources[0]
        self.assertNotIn("findings", row)
        self.assertIn("findings_excerpt", row)
        blob = json.dumps(row)
        # Full evidence must be truncated (ellipsis), not dumped wholesale.
        self.assertNotIn("z" * 300, blob)
        self.assertTrue("…" in blob or "\\u2026" in blob)
        self.assertLess(len(blob), 2000)

    def test_dashboards_agent_view_exists(self) -> None:
        env = self.client.get("/api/agent-view/dashboards/status").json()
        self.assertEqual(env["view"], "dashboards")
        self.assertIn("signoz", env["data"])
        self.assertIn("note", env["data"])

    def test_sessions_list_includes_agent_version(self) -> None:
        rows = self.client.get("/api/sessions?agent_id=agent_j").json()
        match = [r for r in rows if r["session_id"] == "s_robust"]
        self.assertTrue(match)
        self.assertIn("agent_version", match[0])

    def test_recommend_live_false_stays_snapshot(self) -> None:
        from arcnet.model_explore import recommend_models

        out = recommend_models("injection_resist", constraints={"live": False})
        self.assertTrue(out["exploration_only"])
        self.assertEqual(out.get("catalog_source"), "snapshot")
        self.assertTrue(out["recommendations"])

    def test_recommend_live_failure_falls_back_to_snapshot(self) -> None:
        from unittest.mock import MagicMock, patch

        from arcnet.model_explore import recommend_models

        os.environ["OPENAI_API_KEY"] = "sk-test-not-real"
        try:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = RuntimeError("provider down")
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = False
            mock_client.get.return_value = mock_resp
            with patch("arcnet.model_explore.httpx.Client", return_value=mock_client):
                out = recommend_models("injection_resist", constraints={"live": True})
            self.assertTrue(out["exploration_only"])
            self.assertEqual(out.get("catalog_source"), "snapshot_fallback")
            self.assertTrue(out["recommendations"])
            self.assertGreaterEqual(len(out["recommendations"]), 1)
        finally:
            os.environ.pop("OPENAI_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
