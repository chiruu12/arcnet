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
        self.assertEqual(model_catalog.CATALOG_VERSION, "2026-07e")
        ids = {m["id"] for m in model_catalog.list_models()}
        self.assertIn("gpt-5.6-luna", ids)
        self.assertIn("gpt-5.6-sol", ids)
        self.assertIn("claude-opus-5", ids)
        self.assertIn("claude-opus-4-8", ids)
        self.assertIn("claude-sonnet-5", ids)
        self.assertIn("claude-sonnet-4-6", ids)
        self.assertIn("claude-haiku-4-5", ids)
        self.assertIn("kimi-k2.7-code", ids)
        self.assertIn("kimi-k3", ids)
        self.assertIn("deepseek-v4-flash", ids)
        self.assertIn("deepseek-v4-pro", ids)
        self.assertIn("qwen3.8-max-preview", ids)
        self.assertIn("qwen3.6-35b-a3b", ids)
        self.assertEqual(model_catalog.catalog_highlight_ids(), frozenset({
            "kimi-k2.7-code",
            "kimi-k3",
            "qwen3.8-max-preview",
            "qwen3.6-35b-a3b",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        }))
        self.assertIn("gemini-3.1-pro", ids)
        self.assertIn("grok-4.5", ids)
        self.assertIn("legacy-baseline-v1", ids)  # legacy for hero replay pricing
        self.assertIn("catalog list-price estimate as of 2026-07e", model_catalog.price_label())

    def test_project_cost_math(self) -> None:
        from arcnet_server import model_catalog

        c = model_catalog.project_cost_usd(
            "legacy-baseline-v1", input_tokens=1_000_000, output_tokens=1_000_000
        )
        self.assertIsNotNone(c)
        self.assertAlmostEqual(c or 0.0, 0.75, places=8)
        c_cached = model_catalog.project_cost_usd(
            "gpt-5.6-luna",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            use_cached_input=True,
        )
        self.assertAlmostEqual(c_cached or 0.0, 6.1, places=8)
        self.assertIsNone(
            model_catalog.project_cost_usd("not-a-real-model", input_tokens=10, output_tokens=10)
        )

    def test_cached_lte_input(self) -> None:
        from arcnet_server import model_catalog

        for m in model_catalog.list_models():
            inp = float(m["input_usd_per_mtok"])
            cached = float(m["cached_input_usd_per_mtok"])
            if inp > 0:
                self.assertLessEqual(cached, inp, msg=m["id"])


class CatalogApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "cat.db")
        import arcnet_server.main as m

        m._conn = None
        cls.client = TestClient(m.app)

    def test_catalog_endpoint_filters(self) -> None:
        r = self.client.get("/api/models/catalog", params={"status": "current", "reasoning": True})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["catalog_version"], "2026-07e")
        self.assertGreater(body["count"], 5)
        for row in body["models"]:
            self.assertEqual(row["status"], "current")
            self.assertTrue(row["reasoning"])


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
            ("agent_mi", "MI Agent", "support/ops", "forward_facing", "legacy-baseline-v1", ts, ts),
        )
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
                    "legacy-baseline-v1",
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
        self.assertEqual(body["catalog_version"], "2026-07e")
        self.assertEqual(body["current_model"], "legacy-baseline-v1")
        ue = body["usage_evidence"]
        self.assertEqual(ue["session_count"], 2)
        self.assertEqual(ue["input_tokens"], 2000)
        self.assertEqual(ue["output_tokens"], 1000)
        expected_base = (2000 / 1_000_000.0) * 0.15 + (1000 / 1_000_000.0) * 0.6
        self.assertAlmostEqual(body["baseline_projected_cost_usd"], expected_base, places=8)
        self.assertIn("baseline_projected_cost_usd_cached", body)
        self.assertIn("recommendation_buckets", body)

        by_id = {c["id"]: c for c in body["candidates"]}
        self.assertIn("legacy-baseline-v1", by_id)
        self.assertIn("gpt-5.6-luna", by_id)
        self.assertAlmostEqual(by_id["legacy-baseline-v1"]["projected_cost_delta"], 0.0, places=8)
        luna = by_id["gpt-5.6-luna"]
        self.assertIn("projected_cost_usd_cached", luna)
        self.assertIn("fit", luna)
        self.assertIn("bucket", luna)

        # Legacy never outranks current in recommended_upgrade
        upgrades = body["recommendation_buckets"]["recommended_upgrade"]
        for u in upgrades:
            self.assertNotIn(u["status"], ("legacy", "deprecated"))

        rec = body["reasoning_recommendation"]
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertTrue(rec["recommend"])
        self.assertEqual(rec["model_id"], "gpt-5.6-terra")
        self.assertIsInstance(rec["evidence"], list)
        wl = rec["workload"]
        self.assertEqual(wl["threat_count"], 2)
        self.assertEqual(wl["threats_per_session"], 1.0)

    def test_no_reasoning_when_clean(self) -> None:
        conn = self.m.get_conn()
        from arcnet_server.db import now_ms

        ts = now_ms()
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_clean", "Clean", "internal", "internal", "legacy-baseline-v1", ts, ts),
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
                "legacy-baseline-v1",
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

    def test_preview_models_in_candidates(self) -> None:
        r = self.client.get("/api/agents/agent_mi/model-intel")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        by_id = {c["id"]: c for c in body["candidates"]}
        self.assertIn("kimi-k2.7-code", by_id)
        self.assertIn("kimi-k3", by_id)
        self.assertIn("qwen3.8-max-preview", by_id)
        self.assertIn("qwen3.6-35b-a3b", by_id)
        self.assertIn("deepseek-v4-flash", by_id)
        self.assertIn("deepseek-v4-pro", by_id)
        self.assertEqual(by_id["kimi-k3"]["status"], "preview")
        self.assertEqual(by_id["qwen3.8-max-preview"]["status"], "preview")
        hi = {c["id"] for c in body["catalog_highlights"]}
        self.assertEqual(
            hi,
            {
                "kimi-k2.7-code",
                "kimi-k3",
                "qwen3.8-max-preview",
                "qwen3.6-35b-a3b",
                "deepseek-v4-flash",
                "deepseek-v4-pro",
            },
        )
        # preview + current only (legacy baseline may appear if current)
        statuses = {c["status"] for c in body["candidates"]}
        self.assertTrue(statuses <= {"current", "preview", "legacy"})
        self.assertIn("current", statuses)
        self.assertIn("preview", statuses)

    def test_model_intel_toon_format(self) -> None:
        r = self.client.get(
            "/api/agents/agent_mi/model-intel",
            params={"format": "toon"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/toon", r.headers.get("content-type", ""))
        body = r.text
        self.assertIn("catalog_version:", body)
        self.assertIn("kimi-k2.7-code", body)
        self.assertIn("catalog_highlights[", body)

    def test_agent_view_toon_format(self) -> None:
        r = self.client.get(
            "/api/agent-view/fleet_health/all",
            params={"format": "toon"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/toon", r.headers.get("content-type", ""))
        self.assertIn("view: fleet_health", r.text)

    def test_agent_models_toon_format(self) -> None:
        r = self.client.get(
            "/api/agents/agent_mi/models",
            params={"format": "toon"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/toon", r.headers.get("content-type", ""))
        self.assertIn("legacy-baseline-v1", r.text)

    def test_models_catalog_toon_format(self) -> None:
        r = self.client.get("/api/models/catalog", params={"format": "toon"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/toon", r.headers.get("content-type", ""))
        self.assertIn("catalog_version:", r.text)
        self.assertIn("qwen3.6-35b-a3b", r.text)

    def test_versions_timeline_toon_format(self) -> None:
        r = self.client.get(
            "/api/agents/agent_mi/versions/timeline",
            params={"format": "toon"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/toon", r.headers.get("content-type", ""))
        self.assertIn("agent_id:", r.text)


if __name__ == "__main__":
    unittest.main()
