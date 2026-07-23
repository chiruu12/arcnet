"""P8-B — HQ agent-view twins, cross-links, structured errors."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


def _seed(conn) -> None:
    from arcnet_server.db import now_ms

    ts = now_ms()
    conn.execute(
        "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?)",
        ("agent_j", "Agent J", "support", "forward_facing", "gpt-4o-mini", ts, ts),
    )
    conn.execute(
        """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, status,
           trace_id, transcript, started_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            "s_p8b",
            "agent_j",
            "S1",
            "ship order",
            "gpt-4o-mini",
            "failed",
            "trace_p8b",
            json.dumps({"steps": [], "final_output": "blocked"}),
            ts,
        ),
    )
    conn.execute(
        """INSERT INTO threats (threat_id, session_id, agent_id, checkpoint, action,
           category, risk_score, evidence, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        ("thr_p8b", "s_p8b", "agent_j", "tool_call", "block", "leakage", 0.9, "exfil", ts),
    )
    conn.execute(
        """INSERT INTO signals (signal_id, session_id, agent_id, kind, severity,
           reason, source, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        ("sig_hq", "s_p8b", "agent_j", "note", "info", "try gpt-4o", "hq_agent", "pending", ts),
    )
    conn.execute(
        """INSERT INTO hitl_requests (hitl_id, run_id, session_id, payload, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        ("hitl_p8b", "run_1", "s_p8b", json.dumps({"tool": "send_email"}), "pending", ts),
    )
    conn.execute(
        """INSERT INTO replays (replay_id, session_id, candidate_model, runs, verdict,
           created_at, duration_ms) VALUES (?,?,?,?,?,?,?)""",
        (
            "r_p8b",
            "s_p8b",
            "gpt-4o",
            json.dumps([]),
            json.dumps({"recommendation": "promote candidate", "overall": "better"}),
            ts,
            1200,
        ),
    )
    conn.execute(
        """INSERT INTO agent_versions (version_id, agent_id, version, model, created_at)
           VALUES (?,?,?,?,?)""",
        ("av_p8b", "agent_j", "v1", "gpt-4o-mini", ts),
    )
    conn.commit()


class AgentTwinP8BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "p8b.db")
        import arcnet_server.main as m

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app)
        _seed(m.get_conn())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def _env(self, view: str, id_: str) -> dict:
        r = self.client.get(f"/api/agent-view/{view}/{id_}")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        for key in ("view", "id", "data", "links", "hints", "generated_at"):
            self.assertIn(key, body, f"{view}/{id_}")
        return body

    def test_home_twin(self) -> None:
        env = self._env("home", "all")
        self.assertEqual(env["view"], "home")
        self.assertIn("stats", env["data"])
        self.assertIn("loop", env["data"])
        self.assertIn("fleet_health", env["links"])

    def test_fleet_health_twin(self) -> None:
        env = self._env("fleet_health", "all")
        self.assertEqual(env["view"], "fleet_health")
        self.assertEqual(len(env["data"]["agents"]), 1)
        self.assertIn("griffin_status", env["data"])
        self.assertIn("threats", env["links"])

    def test_threats_twins(self) -> None:
        fleet = self._env("threats", "all")
        self.assertEqual(fleet["data"]["scope"], "fleet")
        agent = self._env("threats", "agent_j")
        self.assertEqual(agent["data"]["scope"], "agent")
        session = self._env("threats", "s_p8b")
        self.assertEqual(session["data"]["scope"], "session")
        self.assertEqual(session["data"]["threats"][0]["threat_id"], "thr_p8b")
        self.assertNotIn("evidence", session["data"]["threats"][0])

    def test_hitl_twins(self) -> None:
        all_rows = self._env("hitl", "all")
        self.assertEqual(all_rows["data"]["scope"], "fleet")
        scoped = self._env("hitl", "s_p8b")
        self.assertEqual(scoped["data"]["requests"][0]["hitl_id"], "hitl_p8b")

    def test_hq_agent_twin(self) -> None:
        env = self._env("hq_agent", "agent_j")
        self.assertEqual(env["data"]["agent"]["agent_id"], "agent_j")
        self.assertTrue(any(p["signal_id"] == "sig_hq" for p in env["data"]["proposals"]))
        self.assertIn("models", env["links"])
        self.assertIn("versions", env["links"])
        self.assertIn("apply_endpoint", env["data"])

    def test_case_files_twin(self) -> None:
        env = self._env("case_files", "s_p8b")
        self.assertEqual(env["view"], "case_files")
        self.assertIn("root_cause", env["data"])
        self.assertEqual(env["data"]["export"]["zip"], "/export/case-file/s_p8b")
        self.assertEqual(env["links"]["case_file"], "/export/case-file/s_p8b")

    def test_time_machine_session_and_replay(self) -> None:
        sess = self._env("time_machine", "s_p8b")
        self.assertEqual(sess["data"]["kind"], "session")
        self.assertEqual(sess["data"]["latest_replay_id"], "r_p8b")
        replay = self._env("time_machine", "r_p8b")
        self.assertEqual(replay["data"]["kind"], "replay")
        self.assertIn("verdict", replay["data"])
        self.assertEqual(replay["links"]["replay"], "/api/agent-view/replay/r_p8b")

    def test_sources_trust_alias(self) -> None:
        env = self._env("sources_trust", "agent_j")
        self.assertEqual(env["view"], "sources_trust")
        self.assertIn("sources", env["data"])

    def test_signals_fleet_scope(self) -> None:
        env = self._env("signals", "all")
        self.assertEqual(env["data"]["scope"], "fleet")

    def test_session_cross_links(self) -> None:
        env = self._env("session", "s_p8b")
        links = env["links"]
        self.assertEqual(links["case_file"], "/export/case-file/s_p8b")
        self.assertEqual(links["models"], "/api/agents/agent_j/models")
        self.assertEqual(links["versions"], "/api/agents/agent_j/versions")
        self.assertEqual(links["versions_timeline"], "/api/agents/agent_j/versions/timeline")

    def test_structured_404_with_hint(self) -> None:
        for path in (
            "/api/sessions/s_missing",
            "/api/agent-view/case_files/s_missing",
            "/api/agent-view/hq_agent/nobody",
            "/api/agent-view/time_machine/nobody",
            "/api/agent-view/nonsense/x",
        ):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 404, path)
            body = res.json()
            self.assertIn("detail", body, path)
            self.assertIn("hint", body, path)

    def test_structured_409_duplicate_version(self) -> None:
        first = self.client.post(
            "/api/agents/agent_j/apply-model",
            json={"confirm": True, "model": "gpt-4o-mini", "version": "p8b-v1"},
        )
        self.assertEqual(first.status_code, 200)
        vid = first.json()["version"]["version_id"]
        dup = self.client.post(
            "/api/agents/agent_j/apply-model",
            json={
                "confirm": True,
                "model": "gpt-4o",
                "version": "p8b-v2",
                "version_id": vid,
            },
        )
        self.assertEqual(dup.status_code, 409)
        body = dup.json()
        self.assertIn("detail", body)
        self.assertIn("hint", body)
        self.assertIn("version_id", body["detail"])


if __name__ == "__main__":
    unittest.main()
