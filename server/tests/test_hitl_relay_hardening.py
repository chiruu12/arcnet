"""P32 — HITL relay adversarial probes (hermetic)."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from arcnet_server.hitl_relay import (
    RELAY_MAX_RESPONSE_BYTES,
    _agentos_base,
    _post_agentos,
    _validate_agentos_base,
)


class HitlRelayHardeningTests(unittest.IsolatedAsyncioTestCase):
    def test_validate_rejects_non_http_schemes(self) -> None:
        self.assertIsNone(_validate_agentos_base("file:///etc/passwd"))
        self.assertIsNone(_validate_agentos_base("gopher://evil"))
        self.assertIsNone(_validate_agentos_base("http://"))
        self.assertEqual(
            _validate_agentos_base("http://127.0.0.1:7777"),
            "http://127.0.0.1:7777",
        )

    def test_agentos_base_rejects_ssrf_url(self) -> None:
        with patch.dict(os.environ, {"ARCNET_AGENTOS_URL": "file:///etc/passwd"}):
            self.assertIsNone(_agentos_base())

    async def test_post_skips_body_after_cap(self) -> None:
        chunks = [b"x" * 1024] * (RELAY_MAX_RESPONSE_BYTES // 1024 + 10)

        class _Stream:
            status_code = 500

            async def aiter_bytes(self):
                for chunk in chunks:
                    yield chunk

        stream_ctx = MagicMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=_Stream())
        stream_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=stream_ctx)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("arcnet_server.hitl_relay.httpx.AsyncClient", return_value=mock_client) as mock_cls:
            ok, detail = await _post_agentos("http://agentos.test:7777", {"decision": "approved"})

        self.assertFalse(ok)
        self.assertIn("500", detail)
        mock_client.stream.assert_called_once()
        _, client_kwargs = mock_cls.call_args
        self.assertFalse(client_kwargs.get("follow_redirects", True))

    async def test_post_rejects_invalid_base_without_http(self) -> None:
        ok, detail = await _post_agentos("file:///etc/passwd", {"decision": "approved"})
        self.assertFalse(ok)
        self.assertIn("http(s)", detail)


class HitlRelayApiHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "hitl_hard.db")
        import arcnet_server.main as m

        m._conn = None
        cls.client = TestClient(m.app)

    def setUp(self) -> None:
        os.environ["ARCNET_AGENTOS_URL"] = ""

    def test_invalid_agentos_url_skips_relay_http(self) -> None:
        created = self.client.post(
            "/api/hitl",
            json={"run_id": "run_inv", "session_id": "s_inv", "payload": {}},
        ).json()
        hitl_id = created["hitl_id"]

        with patch("arcnet_server.hitl_relay.httpx.AsyncClient") as mock_client:
            with patch.dict(os.environ, {"ARCNET_AGENTOS_URL": "file:///etc/passwd"}):
                res = self.client.post(f"/api/hitl/{hitl_id}", json={"decision": "approved"})
        self.assertEqual(res.status_code, 200)
        relay = res.json()["relay"]
        self.assertFalse(relay["attempted"])
        mock_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
