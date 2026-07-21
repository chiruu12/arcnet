"""Incident agent-view + Case File exporter (docs/12)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import zipfile


class CaseFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "case.db")
        import arcnet_server.main as m
        from arcnet_server.db import now_ms

        m._conn = None  # tests share the module; force a fresh DB per class
        cls.m = m
        conn = m.get_conn()
        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "Agent J", "support/ops", "forward_facing", "gpt-4o-mini", ts, ts),
        )
        transcript = {
            "session_id": "s_case",
            "scenario": "S1",
            "goal": "check shipping for #4415",
            "steps": [
                {"i": 0, "type": "tool_call", "tool": "fetch_url", "trust_level": "retrieved",
                 "guard": {"checkpoint": "retrieved", "action": "allow"}},
                {"i": 1, "type": "tool_call", "tool": "send_email",
                 "guard": {"checkpoint": "tool_call", "action": "block"}},
                {"i": 2, "type": "model_turn", "output_digest": "abc"},
            ],
        }
        conn.execute(
            """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
               status, outcome, usage, trace_id, transcript, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "s_case", "agent_j", "S1", "check shipping for #4415", "gpt-4o-mini", 0.0,
                "failed", json.dumps({"goal_reached": "failed", "exfil_attempts": 1}),
                json.dumps({"cost_usd": 0.0005}), "trace_abc",
                json.dumps(transcript), ts, ts,
            ),
        )
        conn.execute(
            """INSERT INTO threats (threat_id, session_id, agent_id, checkpoint, action, category,
               subcategory, risk_score, trust_level, evidence, trace_id, span_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("thr_1", "s_case", "agent_j", "tool_call", "block", "taint",
             "retrieved_source_in_side_effect", 0.85, "tool_output", "send_email to edgar", "trace_abc", "span1", ts),
        )
        conn.execute(
            """INSERT INTO replays (replay_id, session_id, candidate_model, candidate_prompt_ref,
               runs, verdict, created_at, duration_ms) VALUES (?,?,?,?,?,?,?,?)""",
            ("r_case", "s_case", "gpt-4o", None, json.dumps([]),
             json.dumps({"verdict": "mixed", "recommendation": "candidate resisted the injection"}), ts, 1000),
        )
        conn.commit()

    def test_incident_envelope_shape(self) -> None:
        env = self.m.agent_view("incident", "s_case")
        self.assertEqual(env["view"], "incident")
        self.assertEqual(env["id"], "s_case")
        data = env["data"]
        self.assertEqual(data["scenario"], "S1")
        self.assertEqual(data["exposure"], "forward_facing")
        self.assertEqual(data["root_cause"]["checkpoint"], "tool_call")
        self.assertEqual(data["root_cause"]["action"], "block")
        self.assertEqual(data["related_replay_id"], "r_case")
        self.assertTrue(any("resisted" in a for a in data["recommended_actions"]))
        self.assertIn("trace_abc", env["links"]["signoz_trace"])

    def test_agent_view_dispatch(self) -> None:
        self.assertEqual(self.m.agent_view("incident", "s_case")["view"], "incident")
        self.assertEqual(self.m.agent_view("session", "s_case")["view"], "session")
        self.assertEqual(self.m.agent_view("fleet", "all")["view"], "fleet")
        self.assertEqual(self.m.agent_view("sources", "s_case")["view"], "sources")
        with self.assertRaises(Exception):
            self.m.agent_view("nonsense", "x")

    def test_case_file_bundle(self) -> None:
        payload, md, env = self.m._case_file_zip_bytes("s_case")
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            names = set(zf.namelist())
            self.assertEqual(names, {"case-file.md", "case-file.json"})
            md_in = zf.read("case-file.md").decode()
            json_in = json.loads(zf.read("case-file.json"))
        self.assertIn("Root cause", md_in)
        self.assertIn("send_email", md_in)
        self.assertIn("Fix-prompt preamble", md_in)
        self.assertEqual(json_in["view"], "incident")


if __name__ == "__main__":
    unittest.main()
