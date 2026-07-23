"""Model catalog integrity + evidence-grounded cost projections (docs/27)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class CatalogIntegrityTests(unittest.TestCase):
    def test_catalog_shape(self) -> None:
        from arcnet_server import model_catalog

        errs = model_catalog.catalog_integrity_errors()
        self.assertEqual(errs, [], msg=errs)
        self.assertEqual(model_catalog.CATALOG_VERSION, "2026-07")
        ids = {m["id"] for m in model_catalog.list_models()}
        # Required coverage classes from packet P8-C
        self.assertTrue(any(i.startswith("gpt-5") for i in ids))
        self.assertTrue({"o3", "o4-mini"} & ids)
        self.assertTrue(any("opus" in i for i in ids))
        self.assertTrue(any("sonnet" in i for i in ids))
        self.assertTrue(any("haiku" in i for i in ids))
        self.assertTrue(any(i.startswith("gemini-3") for i in ids))
        self.assertIn("kimi-k3", ids)
        self.assertTrue(any(i.startswith("grok-4.5") for i in ids))
        self.assertIn("catalog list-price estimate as of 2026-07", model_catalog.price_label())

    def test_project_cost_math(self) -> None:
        from arcnet_server import model_catalog

        # gpt-4o-mini: 0.15 / 0.6 per MTok → 1M in + 1M out = 0.75
        c = model_catalog.project_cost_usd(
            "gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000
        )
        self.assertIsNotNone(c)
        self.assertAlmostEqual(c or 0.0, 0.75, places=8)
        # unknown model → None (never fabricate a price)
        self.assertIsNone(
            model_catalog.project_cost_usd("not-a-real-model", input_tokens=10, output_tokens=10)
        )


class ProjectionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "mi.db")
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
            ("agent_mi", "MI Agent", "support/ops", "forward_facing", "gpt-4o-mini", ts, ts),
        )
        # Deterministic usage: 2 sessions × (1000 in, 500 out)
        for i, sid in enumerate(("s_mi_a", "s_mi_b")):
            conn.execute(
                """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
                   status, outcome, usage, trace_id, transcript, started_at, ended_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    "agent_mi",
                    "S1",
                    "goal",
                    "gpt-4o-mini",
                    0.0,
                    "completed",
                    json.dumps({"goal_reached": "clean"}),
                    json.dumps({"input_tokens": 1000, "output_tokens": 500}),
                    f"trace_{sid}",
                    None,
                    ts - i * 1000,
                    ts,
                ),
            )
        # Hard workload: 2 threats on 2 sessions → threat_rate=1.0
        for i, tid in enumerate(("t_mi_1", "t_mi_2")):
            conn.execute(
                """INSERT INTO threats
                   (threat_id, session_id, agent_id, checkpoint, action, category, subcategory,
                    risk_score, trust_level, evidence, trace_id, span_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    tid,
                    "s_mi_a" if i == 0 else "s_mi_b",
                    "agent_mi",
                    "tool_call",
                    "block",
                    "injection",
                    "prompt_injection",
                    0.9,
                    "retrieved",
                    "tainted",
                    None,
                    None,
                    ts,
                ),
            )
        # One contested replay verdict
        conn.execute(
            """INSERT INTO replays
               (replay_id, session_id, candidate_model, candidate_prompt_ref, runs, verdict,
                created_at, duration_ms)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                "rp_mi_1",
                "s_mi_a",
                "gpt-4o",
                None,
                json.dumps([]),
                json.dumps({"verdict": "improved", "recommendation": "try gpt-4o"}),
                ts,
                10,
            ),
        )
        conn.commit()

    def test_models_endpoint_projections(self) -> None:
        r = self.client.get("/api/agents/agent_mi/model-intel")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["catalog_version"], "2026-07")
        self.assertEqual(body["current_model"], "gpt-4o-mini")
        ue = body["usage_evidence"]
        self.assertEqual(ue["session_count"], 2)
        self.assertEqual(ue["input_tokens"], 2000)
        self.assertEqual(ue["output_tokens"], 1000)
        # gpt-4o-mini list: 0.15/MTok in, 0.6/MTok out
        expected_base = (2000 / 1_000_000.0) * 0.15 + (1000 / 1_000_000.0) * 0.6
        self.assertAlmostEqual(body["baseline_projected_cost_usd"], expected_base, places=8)

        by_id = {c["id"]: c for c in body["candidates"]}
        self.assertIn("gpt-4o-mini", by_id)
        self.assertIn("o4-mini", by_id)
        self.assertAlmostEqual(by_id["gpt-4o-mini"]["projected_cost_delta"], 0.0, places=8)
        o4 = by_id["o4-mini"]
        o4_cost = (2000 / 1_000_000.0) * 1.1 + (1000 / 1_000_000.0) * 4.4
        self.assertAlmostEqual(o4["projected_cost_usd"], o4_cost, places=8)
        self.assertAlmostEqual(
            o4["projected_cost_delta"], o4_cost - expected_base, places=8
        )
        self.assertIn("catalog list-price estimate", o4["price_label"])
        # Observed cascade list still present
        models = {m["model"]: m["session_count"] for m in body["models"]}
        self.assertEqual(models["gpt-4o-mini"], 2)

        rec = body["reasoning_recommendation"]
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertTrue(rec["recommend"])
        self.assertEqual(rec["tier"], "reasoning")
        self.assertIn("threat_rate", rec["rationale"])
        self.assertIn("2 threats", rec["rationale"])
        self.assertEqual(rec["evidence"]["threat_count"], 2)
        self.assertEqual(rec["evidence"]["adversarial_replay_count"], 1)

    def test_no_reasoning_when_clean(self) -> None:
        conn = self.m.get_conn()
        from arcnet_server.db import now_ms

        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_clean", "Clean", "internal", "internal", "gpt-4o-mini", ts, ts),
        )
        conn.execute(
            """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
               status, outcome, usage, trace_id, transcript, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "s_clean",
                "agent_clean",
                "S0",
                "g",
                "gpt-4o-mini",
                0.0,
                "completed",
                json.dumps({}),
                json.dumps({"input_tokens": 100, "output_tokens": 50}),
                None,
                None,
                ts,
                ts,
            ),
        )
        conn.commit()
        r = self.client.get("/api/agents/agent_clean/model-intel")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["reasoning_recommendation"])


if __name__ == "__main__":
    unittest.main()
