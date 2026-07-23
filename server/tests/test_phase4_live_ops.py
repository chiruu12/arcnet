"""Phase 4 — live ops: AgentOS probe, session filters, pagination under list sizes."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[2]

class Phase4LiveOpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls._tmpdir.name) / "phase4.db"
        os.environ["ARCNET_DB_PATH"] = str(cls.db_path)
        os.environ.pop("ARCNET_AGENTOS_URL", None)
        import arcnet_server.main as m

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app)
        cls.client.post(
            "/api/agents",
            json={"agent_id": "agent_j", "name": "J", "model": "gpt-4o-mini"},
        )
        cls.sid = f"s_p4_{int(time.time())}"
        cls.client.post(
            "/api/sessions",
            json={
                "session_id": cls.sid,
                "agent_id": "agent_j",
                "scenario": "S1",
                "goal": "phase4",
                "model": "gpt-4o-mini",
                "status": "completed",
            },
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls._tmpdir.cleanup()

    def test_apply_probe_skipped_without_url(self) -> None:
        os.environ.pop("ARCNET_AGENTOS_URL", None)
        ok = self.client.post(
            "/api/agents/agent_j/apply-model",
            json={
                "confirm": True,
                "model": "gpt-4o",
                "version": f"p4-skip-{time.time_ns()}",
            },
        )
        self.assertEqual(ok.status_code, 200)
        body = ok.json()
        self.assertTrue(body["agentos_reload_required"])
        probe = body["agentos_probe"]
        self.assertFalse(probe["probed"])
        self.assertIsNone(probe["models_match"])
        self.assertIn("unset", probe["note"].lower())

    def test_apply_probe_mismatch_when_reachable(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"model":"gpt-4o-mini"}'
        mock_resp.json.return_value = {"model": "gpt-4o-mini", "process": "agentos"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.dict(os.environ, {"ARCNET_AGENTOS_URL": "http://agentos.test:7777"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                ok = self.client.post(
                    "/api/agents/agent_j/apply-model",
                    json={
                        "confirm": True,
                        "model": "gpt-4o",
                        "version": f"p4-mis-{time.time_ns()}",
                        "session_id": self.sid,
                    },
                )
        self.assertEqual(ok.status_code, 200)
        probe = ok.json()["agentos_probe"]
        self.assertTrue(probe["probed"])
        self.assertTrue(probe["reachable"])
        self.assertEqual(probe["live_model"], "gpt-4o-mini")
        self.assertEqual(probe["sqlite_model"], "gpt-4o")
        self.assertFalse(probe["models_match"])
        self.assertIn("Restart", probe["note"])
        self.assertTrue(ok.json()["agentos_reload_required"])

    def test_apply_probe_match_after_reload(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"model":"gpt-4o"}'
        mock_resp.json.return_value = {"model": "gpt-4o"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.dict(os.environ, {"ARCNET_AGENTOS_URL": "http://agentos.test:7777"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                ok = self.client.post(
                    "/api/agents/agent_j/apply-model",
                    json={
                        "confirm": True,
                        "model": "gpt-4o",
                        "version": f"p4-match-{time.time_ns()}",
                    },
                )
        body = ok.json()
        probe = body["agentos_probe"]
        self.assertTrue(probe["models_match"])
        self.assertIn("match", probe["note"].lower())
        self.assertFalse(body["agentos_reload_required"])
        self.assertIn("no AgentOS restart", body["agentos_reload_instructions"])

    def test_session_filters_agent_version_and_version_id(self) -> None:
        apply = self.client.post(
            "/api/agents/agent_j/apply-model",
            json={
                "confirm": True,
                "model": "gpt-4o",
                "version": f"p4-filt-{time.time_ns()}",
                "session_id": self.sid,
            },
        )
        self.assertEqual(apply.status_code, 200)
        version_id = apply.json()["version"]["version_id"]
        by_av = self.client.get(
            f"/api/sessions?agent_id=agent_j&agent_version={version_id}"
        )
        by_vid = self.client.get(
            f"/api/sessions?agent_id=agent_j&version_id={version_id}"
        )
        self.assertEqual(by_av.status_code, 200)
        self.assertEqual(by_vid.status_code, 200)
        self.assertEqual(
            by_av.headers.get("X-Total-Count"), by_vid.headers.get("X-Total-Count")
        )
        self.assertGreaterEqual(int(by_av.headers.get("X-Total-Count", "0")), 1)
        ids = {r["session_id"] for r in by_av.json()}
        self.assertIn(self.sid, ids)

    def test_signals_total_exceeds_page(self) -> None:
        for i in range(45):
            r = self.client.post(
                "/api/signal",
                json={
                    "agent_id": "agent_j",
                    "kind": "note",
                    "severity": "info",
                    "reason": f"p4 fill {i}",
                    "source": "ops",
                },
            )
            self.assertEqual(r.status_code, 200)
        page = self.client.get("/api/signals?agent_id=agent_j&limit=40&offset=0")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.json()), 40)
        self.assertGreater(int(page.headers.get("X-Total-Count", "0")), 40)


class Phase4LiveOpsScriptTests(unittest.TestCase):
    def test_live_ops_dry_run_script_exits_zero(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{_ROOT / 'sdk'}:{_ROOT / 'server'}"
        env.pop("ARCNET_AGENTOS_URL", None)
        proc = subprocess.run(
            [sys.executable, str(_ROOT / "scripts" / "live_ops_dry_run.py")],
            cwd=str(_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )
        self.assertIn("live_ops OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
