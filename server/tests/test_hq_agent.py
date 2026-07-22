"""HQ Agent — version registry APIs + hq_tools (mocked HTTP where needed)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class AgentVersionRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmpdir.name) / "hq.db"
        os.environ["ARCNET_DB_PATH"] = str(cls.db_path)
        import arcnet_server.main as m

        m._conn = None
        cls.client = TestClient(m.app)
        cls.client.post(
            "/api/agents",
            json={
                "agent_id": "agent_j",
                "name": "Agent J",
                "exposure": "forward_facing",
                "model": "gpt-4o-mini",
            },
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls._tmpdir.cleanup()

    def test_create_list_timeline(self) -> None:
        created = self.client.post(
            "/api/agents/agent_j/versions",
            json={
                "version": "2026-07-22.1",
                "model": "gpt-4o-mini",
                "source_ref": "git:deadbeef",
                "notes": "baseline",
            },
        )
        self.assertEqual(created.status_code, 200)
        body = created.json()
        self.assertEqual(body["version"], "2026-07-22.1")
        self.assertTrue(str(body["version_id"]).startswith("av_"))

        listed = self.client.get("/api/agents/agent_j/versions")
        self.assertEqual(listed.status_code, 200)
        self.assertGreaterEqual(int(listed.headers.get("X-Total-Count", "0")), 1)
        self.assertTrue(any(r["version"] == "2026-07-22.1" for r in listed.json()))

        tl = self.client.get("/api/agents/agent_j/versions/timeline")
        self.assertEqual(tl.status_code, 200)
        data = tl.json()
        self.assertEqual(data["agent_id"], "agent_j")
        self.assertEqual(data["current_model"], "gpt-4o-mini")
        self.assertTrue(data["versions"])

    def test_create_requires_version(self) -> None:
        r = self.client.post("/api/agents/agent_j/versions", json={"model": "gpt-4o"})
        self.assertEqual(r.status_code, 400)


class HqToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmpdir.name) / "hq_tools.db"
        os.environ["ARCNET_DB_PATH"] = str(cls.db_path)
        import arcnet_server.main as m

        m._conn = None
        cls.main = m
        cls.client = TestClient(m.app)
        cls.client.post(
            "/api/agents",
            json={"agent_id": "agent_j", "name": "J", "model": "gpt-4o-mini"},
        )
        # Point tools at the TestClient ASGI app via httpx transport override:
        # use real server URL pattern by patching _base to talk through TestClient.
        cls.base = "http://testserver"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls._tmpdir.cleanup()

    def test_register_propose_via_tools(self) -> None:
        from arcnet import hq_tools

        transport = self.client
        # Use httpx ASGI transport through TestClient by monkeypatching get/post
        with patch.object(hq_tools, "_get") as g, patch.object(hq_tools, "_post") as p:

            def get_side(path: str, *, server_url: str | None = None, timeout: float = 10.0):
                r = transport.get(path)
                r.raise_for_status()
                return r.json()

            def post_side(
                path: str,
                body: dict,
                *,
                server_url: str | None = None,
                timeout: float = 10.0,
            ):
                r = transport.post(path, json=body)
                r.raise_for_status()
                return r.json()

            g.side_effect = get_side
            p.side_effect = post_side

            ver = hq_tools.register_agent_version(
                "agent_j", "v-tools-1", model="gpt-4o", notes="from tools"
            )
            self.assertEqual(ver["version"], "v-tools-1")

            prop = hq_tools.propose_model_change(
                "agent_j",
                "gpt-4o",
                "injection_resist upgrade",
                from_model="gpt-4o-mini",
                task_type="injection_resist",
            )
            self.assertEqual(prop["source"], "hq_agent")
            self.assertEqual(prop["kind"], "note")

            proposals = hq_tools.list_model_proposals(agent_id="agent_j")
            self.assertTrue(any(x["signal_id"] == prop["signal_id"] for x in proposals))

            tl = hq_tools.agent_version_timeline("agent_j")
            self.assertTrue(any(v["version"] == "v-tools-1" for v in tl["versions"]))

    def test_griffin_anomalies_labels_mad(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_get") as g:

            def get_side(path: str, *, server_url: str | None = None, timeout: float = 10.0):
                if path.startswith("/api/griffin/status"):
                    return {"model": "mad", "status": "cold", "anomalies": []}
                if path.startswith("/api/signals"):
                    return [
                        {
                            "signal_id": "sig_x",
                            "source": "griffin",
                            "kind": "note",
                            "reason": "outlier",
                        }
                    ]
                raise AssertionError(path)

            g.side_effect = get_side
            out = hq_tools.griffin_anomalies()
            self.assertEqual(out["estimator"], "mad")
            self.assertIn("MAD", out["note"])
            self.assertEqual(len(out["recent_griffin_signals"]), 1)

    def test_recommend_models_local(self) -> None:
        from arcnet import hq_tools

        rec = hq_tools.recommend_models("tool_heavy")
        self.assertIn("recommendations", rec)


class HqAgentBuildSmoke(unittest.TestCase):
    def test_recommend_only_no_agent_import(self) -> None:
        """Product core must not need agents/ to recommend models."""
        from arcnet.hq_tools import recommend_models

        rec = recommend_models("cheap_batch")
        self.assertIn("recommendations", rec)


if __name__ == "__main__":
    unittest.main()
