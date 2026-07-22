"""Pagination, agent signals twin, session check, cascade filters (docs/12 additive / R1)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


def _transcript() -> dict:
    return {
        "session_id": "s_page",
        "scenario": "S1",
        "goal": "check shipping",
        "steps": [
            {"i": 0, "type": "model_turn", "output_digest": "d0"},
            {
                "i": 1,
                "type": "tool_call",
                "tool": "fetch_url",
                "args": {"url": "http://example.test"},
                "recorded_output": "HUGE-SECRET-PAYLOAD " + ("x" * 500),
                "trust_level": "retrieved",
            },
        ],
        "final_output": "done",
    }


class ProductReworkApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "r1.db")
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
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_l", "Agent L", "support/ops", "internal", "gpt-4o", ts, ts),
        )
        for i, (sid, model, agent) in enumerate(
            [
                ("s_page_a", "gpt-4o-mini", "agent_j"),
                ("s_page_b", "gpt-4o-mini", "agent_j"),
                ("s_page_c", "gpt-4o", "agent_j"),
                ("s_page_d", "gpt-4o", "agent_l"),
            ]
        ):
            conn.execute(
                """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
                   status, outcome, usage, trace_id, transcript, started_at, ended_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    agent,
                    "S1" if i < 3 else "S0",
                    "goal",
                    model,
                    0.0,
                    "completed",
                    json.dumps({"goal_reached": "clean"}),
                    json.dumps({"cost_usd": 0.01}),
                    f"trace_{sid}",
                    json.dumps(_transcript()),
                    ts - i * 1000,
                    ts,
                ),
            )
        for i in range(5):
            conn.execute(
                """INSERT INTO signals
                   (signal_id, session_id, agent_id, kind, severity, reason, evidence_link,
                    guidance, source, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"sig_page_{i}",
                    "s_page_a" if i < 3 else None,
                    "agent_j",
                    "steer" if i % 2 == 0 else "note",
                    "warn",
                    f"reason body {i} " + ("y" * 80),
                    None,
                    f"guidance body {i}",
                    "inline",
                    "pending" if i < 2 else "acted",
                    ts - i,
                ),
            )
        conn.execute(
            """INSERT INTO threats
               (threat_id, session_id, agent_id, checkpoint, action, category, subcategory,
                risk_score, trust_level, evidence, trace_id, span_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "thr_page",
                "s_page_a",
                "agent_j",
                "tool_call",
                "block",
                "injection",
                "ignore_previous",
                0.9,
                "retrieved",
                "blocked exfil attempt",
                "trace_s_page_a",
                None,
                ts,
            ),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_sessions_pagination_headers(self) -> None:
        r = self.client.get("/api/sessions?agent_id=agent_j&limit=2&offset=0")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 2)
        self.assertEqual(r.headers.get("X-Total-Count"), "3")
        self.assertEqual(r.headers.get("X-Limit"), "2")
        self.assertEqual(r.headers.get("X-Offset"), "0")
        r2 = self.client.get("/api/sessions?agent_id=agent_j&limit=2&offset=2")
        self.assertEqual(len(r2.json()), 1)
        self.assertEqual(r2.headers.get("X-Total-Count"), "3")

    def test_sessions_model_filter(self) -> None:
        r = self.client.get("/api/sessions?agent_id=agent_j&model=gpt-4o")
        self.assertEqual(r.status_code, 200)
        rows = r.json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_id"], "s_page_c")
        self.assertEqual(r.headers.get("X-Total-Count"), "1")

    def test_agent_models_cascade(self) -> None:
        r = self.client.get("/api/agents/agent_j/models")
        self.assertEqual(r.status_code, 200)
        models = {row["model"]: row["session_count"] for row in r.json()}
        self.assertEqual(models["gpt-4o-mini"], 2)
        self.assertEqual(models["gpt-4o"], 1)
        missing = self.client.get("/api/agents/nope/models")
        self.assertEqual(missing.status_code, 404)

    def test_signals_pagination_and_agent_filter(self) -> None:
        r = self.client.get("/api/signals?agent_id=agent_j&limit=2&offset=1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 2)
        self.assertEqual(r.headers.get("X-Total-Count"), "5")

    def test_agent_view_signals(self) -> None:
        r = self.client.get("/api/agent-view/signals/agent_j")
        self.assertEqual(r.status_code, 200)
        env = r.json()
        self.assertEqual(env["view"], "signals")
        self.assertEqual(env["data"]["scope"], "agent")
        self.assertEqual(env["data"]["total"], 5)
        sig = env["data"]["signals"][0]
        self.assertIn("reason_excerpt", sig)
        self.assertNotIn("reason", sig)
        self.assertTrue(len(sig["reason_excerpt"]) <= 200)
        # session scope
        r2 = self.client.get("/api/agent-view/signals/s_page_a")
        self.assertEqual(r2.json()["data"]["scope"], "session")
        self.assertGreaterEqual(r2.json()["data"]["total"], 3)
        bad = self.client.get("/api/agent-view/signals/unknown_ref")
        self.assertEqual(bad.status_code, 404)

    def test_agent_view_session_check(self) -> None:
        r = self.client.get("/api/agent-view/check/s_page_a")
        self.assertEqual(r.status_code, 200)
        env = r.json()
        self.assertEqual(env["view"], "check")
        data = env["data"]
        self.assertEqual(data["session"]["session_id"], "s_page_a")
        self.assertEqual(data["counts"]["threats"], 1)
        self.assertGreaterEqual(data["counts"]["signals"], 3)
        self.assertEqual(data["top_threat"]["action"], "block")
        blob = json.dumps(data)
        self.assertNotIn("HUGE-SECRET-PAYLOAD", blob)
        self.assertNotIn("recorded_output", blob)
        missing = self.client.get("/api/agent-view/check/s_missing")
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
