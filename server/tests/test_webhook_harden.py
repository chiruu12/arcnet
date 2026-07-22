"""Webhook + SigNoz status hardening (verify-reinforce)."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class WebhookHardenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "webhook.db")
        import arcnet_server.main as m

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_array_body_is_400_not_500(self) -> None:
        res = self.client.post("/webhooks/signoz", json=[])
        self.assertEqual(res.status_code, 400)
        self.assertIn("JSON object", res.json()["detail"])

    def test_alerts_must_be_list(self) -> None:
        res = self.client.post("/webhooks/signoz", json={"alerts": "nope"})
        self.assertEqual(res.status_code, 400)

    def test_oversized_agent_id_is_clipped(self) -> None:
        huge = "x" * 5000
        res = self.client.post(
            "/webhooks/signoz",
            json={
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "fingerprint": "fp-clip-test",
                        "labels": {
                            "agent_id": huge,
                            "session_id": "s_" + ("y" * 500),
                            "arcnet_kind": "steer",
                            "alertname": "arcnet.probe",
                        },
                        "annotations": {"summary": "clip me"},
                    }
                ],
            },
        )
        self.assertEqual(res.status_code, 204)
        rows = self.client.get("/api/signals?limit=20").json()
        match = [s for s in rows if s.get("reason") == "clip me"]
        self.assertTrue(match, rows)
        self.assertEqual(len(match[0]["agent_id"]), self.m.WEBHOOK_ID_MAX)
        self.assertEqual(len(match[0]["session_id"]), self.m.WEBHOOK_ID_MAX)

    def test_empty_object_is_204(self) -> None:
        self.assertEqual(self.client.post("/webhooks/signoz", json={}).status_code, 204)

    def test_webhook_secret_required_when_configured(self) -> None:
        prev = os.environ.get("ARCNET_WEBHOOK_SECRET")
        os.environ["ARCNET_WEBHOOK_SECRET"] = "test-secret-xyz"
        try:
            denied = self.client.post("/webhooks/signoz", json={})
            self.assertEqual(denied.status_code, 401)
            ok = self.client.post(
                "/webhooks/signoz",
                headers={"X-ArcNet-Webhook-Secret": "test-secret-xyz"},
                json={},
            )
            self.assertEqual(ok.status_code, 204)
            bearer = self.client.post(
                "/webhooks/signoz",
                headers={"Authorization": "Bearer test-secret-xyz"},
                json={},
            )
            self.assertEqual(bearer.status_code, 204)
        finally:
            if prev is None:
                os.environ.pop("ARCNET_WEBHOOK_SECRET", None)
            else:
                os.environ["ARCNET_WEBHOOK_SECRET"] = prev


class SignozStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "status.db")
        import arcnet_server.main as m

        m._conn = None
        cls.m = m
        cls.client = TestClient(m.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m._conn = None

    def test_status_probes_query_range_not_version(self) -> None:
        os.environ["SIGNOZ_URL"] = "http://signoz.test"
        os.environ["SIGNOZ_API_KEY"] = "test-key"

        def fake_request(method, url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if method == "GET":
                return resp
            self.assertIn("/api/v5/query_range", str(url))
            self.assertEqual(kwargs.get("headers", {}).get("SIGNOZ-API-KEY"), "test-key")
            resp.status_code = 200
            return resp

        with patch("arcnet_server.main.httpx.get", side_effect=lambda *a, **k: fake_request("GET", *a, **k)):
            with patch(
                "arcnet_server.main.httpx.post",
                side_effect=lambda *a, **k: fake_request("POST", *a, **k),
            ):
                body = self.client.get("/api/signoz/status").json()
        self.assertTrue(body["api_key_present"])
        self.assertTrue(body["query_range_ok"])
        self.assertIn("query_range", body["query_note"])


if __name__ == "__main__":
    unittest.main()
