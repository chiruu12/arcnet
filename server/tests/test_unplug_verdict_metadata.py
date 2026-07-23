"""P8-D — guard verdict metadata persisted on threats, sources, and signals."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class UnplugVerdictMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "verdict.db")
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
                "s_meta",
                "agent_j",
                "S1",
                "goal",
                "gpt-4o-mini",
                0.0,
                "completed",
                json.dumps({"goal_reached": "failed"}),
                json.dumps({"cost_usd": 0.01}),
                "trace_meta",
                json.dumps({"steps": [], "final_output": "x"}),
                ts,
                ts,
            ),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_threat_ingest_stores_findings_detail(self) -> None:
        payload = {
            "threat_id": "thr_meta",
            "session_id": "s_meta",
            "agent_id": "agent_j",
            "checkpoint": "input",
            "action": "block",
            "category": "injection",
            "subcategory": "ignore_previous",
            "pattern_class": "regex",
            "risk_score": 0.85,
            "evidence": "Matched pattern: ignore_previous",
            "findings_detail": [
                {
                    "category": "injection",
                    "subcategory": "ignore_previous",
                    "stage": "regex",
                    "score": 0.85,
                    "evidence": "Matched pattern: ignore_previous",
                }
            ],
            "guard_verdict": {
                "checkpoint": "input",
                "action": "block",
                "rule": "ignore_previous",
                "pattern_class": "regex",
                "risk_score": 0.85,
            },
        }
        row = self.client.post("/api/threats", json=payload).json()
        self.assertEqual(row["pattern_class"], "regex")
        self.assertIsInstance(row["findings_detail"], list)
        self.assertEqual(row["findings_detail"][0]["subcategory"], "ignore_previous")
        listed = self.client.get("/api/threats").json()
        hit = next(t for t in listed if t["threat_id"] == "thr_meta")
        self.assertEqual(hit["guard_verdict"]["rule"], "ignore_previous")

    def test_source_ingest_stores_findings_detail(self) -> None:
        payload = {
            "source_id": "src_meta",
            "session_id": "s_meta",
            "agent_id": "agent_j",
            "origin": "fetch_url",
            "trust_level": "retrieved",
            "scan_action": "allow",
            "findings": 1,
            "findings_detail": [
                {
                    "category": "injection",
                    "subcategory": "carrier_protocol",
                    "stage": "regex",
                    "score": 0.2,
                    "evidence": "carrier release",
                }
            ],
            "guard_verdict": {
                "checkpoint": "retrieved",
                "action": "allow",
                "rule": "carrier_protocol",
                "pattern_class": "regex",
            },
        }
        row = self.client.post("/api/sources", json=payload).json()
        self.assertEqual(row["findings"], 1)
        self.assertIsInstance(row["findings_detail"], list)
        env = self.client.get("/api/agent-view/sources/s_meta").json()
        src = env["data"]["sources"][0]
        self.assertEqual(src["guard_verdict"]["rule"], "carrier_protocol")
        self.assertEqual(src["findings_excerpt"][0]["rule"], "carrier_protocol")

    def test_signal_ingest_stores_guard_verdict(self) -> None:
        payload = {
            "session_id": "s_meta",
            "agent_id": "agent_j",
            "kind": "steer",
            "severity": "critical",
            "reason": "blocked tool_call send_email",
            "guidance": "use trusted tools only",
            "source": "inline",
            "guard_verdict": {
                "checkpoint": "tool_call",
                "action": "block",
                "rule": "retrieved_source_in_side_effect",
                "pattern_class": "policy",
                "risk_score": 0.85,
            },
        }
        row = self.client.post("/api/signal", json=payload).json()
        self.assertEqual(row["guard_verdict"]["rule"], "retrieved_source_in_side_effect")
        env = self.client.get("/api/agent-view/signals/s_meta").json()
        sig = next(s for s in env["data"]["signals"] if s["signal_id"] == row["signal_id"])
        self.assertEqual(sig["guard_verdict"]["pattern_class"], "policy")
        self.assertNotIn("guidance", sig)


if __name__ == "__main__":
    unittest.main()
