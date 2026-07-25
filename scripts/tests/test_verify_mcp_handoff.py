"""Hermetic tests for scripts/verify_mcp_handoff.py (no live network)."""

from __future__ import annotations

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_mcp_handoff as vmh  # noqa: E402


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("case-file.md", "# Root cause\nblocked\n")
        zf.writestr("case-file.json", json.dumps({"view": "incident", "id": "s_x"}))
    return buf.getvalue()


class VerifyHandoffTests(unittest.TestCase):
    def test_resolve_trace_from_threats(self) -> None:
        incident = {"links": {"signoz_trace": None}}
        threats = {
            "data": {
                "threats": [{"trace_id": "abc123def456"}],
            }
        }
        tid = vmh._resolve_trace_id(incident, threats, {})
        self.assertEqual(tid, "abc123def456")

    def test_redact_strips_api_key(self) -> None:
        out = vmh._redact("key=supersecret", ["supersecret"])
        self.assertNotIn("supersecret", out)
        self.assertIn("[REDACTED]", out)

    @patch("verify_mcp_handoff.httpx.Client")
    def test_server_down_exits_1(self, client_cls: MagicMock) -> None:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = MagicMock(status_code=0, json=lambda: {"error": "refused"})

        def _get(url: str) -> MagicMock:
            return MagicMock(status_code=503, text="down")

        client.get.side_effect = _get
        report = vmh.verify(server_url="http://127.0.0.1:9", session_id="s_x", signoz_url_override=None, timeout=1.0)
        self.assertEqual(report.exit_code, 1)
        self.assertIn("FAIL", report.verdict)

    @patch("verify_mcp_handoff.httpx.Client")
    def test_handoff_ok_signoz_unreachable_exits_2(self, client_cls: MagicMock) -> None:
        client = client_cls.return_value.__enter__.return_value
        incident = {
            "view": "incident",
            "data": {"scenario": "S1", "root_cause": {"checkpoint": "tool_call"}},
            "links": {"signoz_trace": None},
        }
        threats = {"data": {"threats": [{"trace_id": "trace_deadbeef"}]}}
        status = {
            "signoz_url": "http://127.0.0.1:9",
            "ui_reachable": False,
            "api_key_present": True,
            "query_range_ok": False,
            "query_note": "connection refused",
        }
        evidence = {"trace_id": None, "note": "no trace_id on session", "spans": []}

        def route(url: str) -> MagicMock:
            if url.endswith("/health"):
                return MagicMock(status_code=200, json=lambda: {"ok": True})
            if "/incident/" in url:
                return MagicMock(status_code=200, json=lambda: incident)
            if "/threats/" in url:
                return MagicMock(status_code=200, json=lambda: threats)
            if "/api/signoz/status" in url:
                return MagicMock(status_code=200, json=lambda: status)
            if "/api/signoz/evidence" in url:
                return MagicMock(status_code=200, json=lambda: evidence)
            raise AssertionError(url)

        client.get.side_effect = lambda url: route(url)
        client.post.side_effect = lambda *a, **k: (_ for _ in ()).throw(
            vmh.httpx.ConnectError("refused")
        )
        zip_resp = MagicMock(status_code=200, content=_zip_bytes())
        orig_get = client.get.side_effect

        def get_with_zip(url: str) -> MagicMock:
            if "/export/case-file/" in url:
                return zip_resp
            return orig_get(url)

        client.get.side_effect = get_with_zip

        with patch.dict("os.environ", {"SIGNOZ_API_KEY": "test-key-local"}):
            report = vmh.verify(
                server_url="http://localhost:8000",
                session_id="s_ecfdb55d",
                signoz_url_override="http://127.0.0.1:9",
                timeout=1.0,
            )
        self.assertEqual(report.exit_code, 2)
        self.assertIn("DEGRADED", report.verdict)
        rendered = report.render()
        self.assertIn("case_file_zip", rendered)
        self.assertNotIn("test-key-local", rendered)


if __name__ == "__main__":
    unittest.main()
