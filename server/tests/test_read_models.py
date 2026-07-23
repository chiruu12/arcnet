"""Human vs agent read models: shared records, intentionally different projections (docs/13)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from arcnet_server.read_models import (
    ARG_EXCERPT_CHARS,
    EXCERPT_CHARS,
    FULL_TRANSCRIPT_HATCH_KEY,
    full_transcript_hatch,
)

LARGE_TOOL_OUTPUT = "SECRET-PAYLOAD " + ("lorem ipsum dolor sit amet " * 400)
GIANT_TEXT = "Z" * 5000


def _transcript() -> dict:
    return {
        "session_id": "s_rm",
        "scenario": "S1",
        "goal": "check shipping for #4415",
        "steps": [
            {"i": 0, "type": "model_turn", "output_digest": "d0"},
            {
                "i": 1,
                "type": "tool_call",
                "tool": "fetch_url",
                "args": {"url": "http://bug-planet.net/shipping"},
                "recorded_output": LARGE_TOOL_OUTPUT,
                "trust_level": "retrieved",
                "guard": {"checkpoint": "retrieved", "action": "allow", "top_category": None},
            },
            {
                "i": 2,
                "type": "tool_call",
                "tool": "send_email",
                "args": {"to": "edgar [at] bug-planet [dot] net"},
                "recorded_output": None,
                "guard": {"checkpoint": "tool_call", "action": "block"},
            },
        ],
        "final_output": "order #4415 is in transit",
    }


class ReadModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "rm.db")
        import arcnet_server.main as m
        from arcnet_server.db import now_ms

        m._conn = None  # tests share the module; force a fresh DB per class
        cls.m = m
        cls.client = TestClient(m.app)
        conn = m.get_conn()
        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "Agent J", "support/ops", "forward_facing", "gpt-4o-mini", ts, ts),
        )
        conn.execute(
            """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
               status, outcome, usage, trace_id, transcript, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "s_rm", "agent_j", "S1", "check shipping for #4415", "gpt-4o-mini", 0.0,
                "failed", json.dumps({"goal_reached": "failed", "exfil_attempts": 1}),
                json.dumps({"cost_usd": 0.0005}), "trace_rm",
                json.dumps(_transcript()), ts, ts,
            ),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_projections_share_records_but_differ(self) -> None:
        human = self.client.get("/api/sessions/s_rm?include=transcript").json()
        agent = self.client.get("/api/agent-view/session/s_rm").json()

        # Same underlying record…
        self.assertEqual(human["session_id"], agent["data"]["session"]["session_id"])
        self.assertEqual(human["trace_id"], agent["data"]["session"]["trace_id"])
        self.assertEqual(human["outcome"], agent["data"]["outcome"])

        # …but the human view carries the full replay transcript,
        self.assertEqual(
            human["transcript"]["steps"][1]["recorded_output"], LARGE_TOOL_OUTPUT
        )
        # while the agent view is a bounded evidence timeline with pointers.
        raw = json.dumps(agent)
        self.assertNotIn("SECRET-PAYLOAD", raw)
        step = agent["data"]["timeline"][1]
        self.assertEqual(step["tool"], "fetch_url")
        self.assertEqual(step["recorded_output_chars"], len(LARGE_TOOL_OUTPUT))
        self.assertIn("recorded_output_sha256", step)
        self.assertEqual(step["guard"]["action"], "allow")
        self.assertEqual(
            agent["data"][FULL_TRANSCRIPT_HATCH_KEY],
            full_transcript_hatch("s_rm"),
        )

    def test_full_transcript_hatch_is_intentional_pointer(self) -> None:
        """A15: bounded agent-view + explicit human API pointer (localhost trust)."""
        agent = self.client.get("/api/agent-view/session/s_rm").json()
        hatch = agent["data"][FULL_TRANSCRIPT_HATCH_KEY]
        self.assertEqual(hatch, "/api/sessions/s_rm?include=transcript")
        self.assertNotIn(LARGE_TOOL_OUTPUT, json.dumps(agent))
        human = self.client.get(hatch).json()
        self.assertEqual(
            human["transcript"]["steps"][1]["recorded_output"], LARGE_TOOL_OUTPUT
        )

    def test_excerpt_bounds_incident_and_signals(self) -> None:
        conn = self.m.get_conn()
        from arcnet_server.db import now_ms

        ts = now_ms()
        conn.execute(
            """INSERT INTO threats (threat_id, session_id, agent_id, checkpoint, action, category,
               subcategory, risk_score, trust_level, evidence, trace_id, span_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "thr_big", "s_rm", "agent_j", "tool_call", "block", "leakage",
                "pii", 0.9, "tool_output", GIANT_TEXT, "trace_rm", "span1", ts,
            ),
        )
        conn.execute(
            """INSERT INTO signals (signal_id, session_id, agent_id, kind, severity,
               reason, guidance, source, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                "sig_big", "s_rm", "agent_j", "steer", "warn",
                GIANT_TEXT, GIANT_TEXT, "inline", "pending", ts,
            ),
        )
        conn.execute(
            "UPDATE sessions SET goal=? WHERE session_id=?",
            (GIANT_TEXT, "s_rm"),
        )
        conn.commit()

        incident = self.client.get("/api/agent-view/incident/s_rm").json()
        rc = incident["data"]["root_cause"]
        self.assertLessEqual(len(rc["evidence_excerpt"]), EXCERPT_CHARS)
        self.assertNotIn(GIANT_TEXT, json.dumps(incident))
        self.assertLessEqual(len(incident["data"]["goal"]), EXCERPT_CHARS)

        signals = self.client.get("/api/agent-view/signals/s_rm").json()
        sig = next(s for s in signals["data"]["signals"] if s["signal_id"] == "sig_big")
        self.assertLessEqual(len(sig["reason_excerpt"]), EXCERPT_CHARS)
        self.assertLessEqual(len(sig["guidance_excerpt"]), EXCERPT_CHARS)
        self.assertNotIn("reason", sig)
        self.assertNotIn("guidance", sig)
        self.assertNotIn(GIANT_TEXT, json.dumps(signals))

        session = self.client.get("/api/agent-view/session/s_rm").json()
        step = session["data"]["timeline"][1]
        self.assertLessEqual(len(step["args_excerpt"]), ARG_EXCERPT_CHARS)
        self.assertLessEqual(len(session["data"]["final_output_excerpt"]), EXCERPT_CHARS)

    def test_human_session_excludes_transcript_by_default(self) -> None:
        human = self.client.get("/api/sessions/s_rm").json()
        self.assertNotIn("transcript", human)

    def test_case_file_is_bounded(self) -> None:
        payload, md, env = self.m._case_file_zip_bytes("s_rm")
        self.assertNotIn("SECRET-PAYLOAD", md)
        self.assertNotIn("SECRET-PAYLOAD", json.dumps(env))
        self.assertIn("send_email", md)

    def test_agent_fleet_wraps_human_rows(self) -> None:
        human = self.client.get("/api/fleet").json()
        agent = self.client.get("/api/agent-view/fleet/all").json()
        self.assertEqual(agent["data"]["agents"], human)
        self.assertEqual(agent["view"], "fleet")


class ContractTests(unittest.TestCase):
    """Empty DB, missing ids, validation, ordering, signal attribution."""

    def setUp(self) -> None:
        # Fresh DB per test — these tests mutate rows and assert empty shapes.
        self._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(self._tmp, "contract.db")
        import arcnet_server.main as m

        m._conn = None
        self.m = m
        self.client = TestClient(m.app)

    def tearDown(self) -> None:
        self.m._conn = None

    def test_empty_db_shapes(self) -> None:
        for path in ("/api/fleet", "/api/sessions", "/api/threats", "/api/sources",
                     "/api/signals", "/api/replays"):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, path)
            self.assertEqual(res.json(), [], path)

    def test_missing_ids_are_404(self) -> None:
        for path in (
            "/api/sessions/s_nope",
            "/api/agent-view/incident/s_nope",
            "/api/agent-view/session/s_nope",
            "/api/agent-view/sources/nobody",
            "/api/agent-view/replay/r_nope",
            "/api/agent-view/nonsense/x",
            "/export/case-file/s_nope",
        ):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 404, path)
            self.assertIn("detail", res.json(), path)

    def test_replay_validation(self) -> None:
        res = self.client.post("/api/replay", json={"candidate_model": "gpt-4o"})
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/api/replay", json={"session_id": "s_x"})
        self.assertEqual(res.status_code, 400)
        res = self.client.post(
            "/api/replay", json={"session_id": "s_nope", "candidate_model": "gpt-4o"}
        )
        self.assertEqual(res.status_code, 404)

    def test_limit_validation(self) -> None:
        for path in ("/api/sessions", "/api/signals", "/api/replays"):
            self.assertEqual(self.client.get(f"{path}?limit=0").status_code, 422, path)
            self.assertEqual(self.client.get(f"{path}?limit=1000").status_code, 422, path)
            self.assertEqual(self.client.get(f"{path}?limit=1").status_code, 200, path)

    def test_signal_attribution_matches_sse_rule(self) -> None:
        from arcnet_server.repository import signal_matches_session

        conn = self.m.get_conn()
        rows = [
            ("sig_a", "s_one", "agent_j"),   # session-scoped
            ("sig_b", None, "agent_j"),      # fleet-wide (griffin/alert)
            ("sig_c", "s_two", "agent_j"),   # another session
        ]
        for signal_id, session_id, agent_id in rows:
            conn.execute(
                """INSERT INTO signals (signal_id, session_id, agent_id, kind, severity,
                   reason, source, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                (signal_id, session_id, agent_id, "note", "info", "t", "inline", "pending", 1000),
            )
        conn.commit()

        rest = self.client.get("/api/signals?session_id=s_one").json()
        rest_ids = {s["signal_id"] for s in rest}
        live_ids = {
            signal_id
            for signal_id, session_id, _ in rows
            if signal_matches_session({"session_id": session_id}, "s_one")
        }
        self.assertEqual(rest_ids, live_ids)
        self.assertEqual(rest_ids, {"sig_a", "sig_b"})

    def test_deterministic_ordering_tiebreak(self) -> None:
        conn = self.m.get_conn()
        conn.execute(
            "INSERT INTO agents (agent_id, name, first_seen, last_seen) VALUES ('agent_j','J',1,1)"
        )
        for sid in ("s_aaa", "s_zzz", "s_mmm"):
            conn.execute(
                "INSERT INTO sessions (session_id, agent_id, status, started_at) VALUES (?,?,?,?)",
                (sid, "agent_j", "completed", 5000),
            )
        conn.commit()
        listed = [s["session_id"] for s in self.client.get("/api/sessions").json()]
        self.assertEqual(listed, ["s_zzz", "s_mmm", "s_aaa"])


if __name__ == "__main__":
    unittest.main()
