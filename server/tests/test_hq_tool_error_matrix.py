"""HQ tool error matrix — timeout / 4xx / 5xx → stable {ok:false,error,tool}.

Phase 2 exit: each public hq_tools surface has ≥1 error-path unit;
recommend/propose always carry evidence_refs or an explicit empty reason.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "http://test/x")
    resp = httpx.Response(status, request=req, text=f"boom-{status}")
    return httpx.HTTPStatusError(f"{status}", request=req, response=resp)


class HqToolErrorMatrixTests(unittest.TestCase):
    """Structured envelopes for HTTP-backed tools via _get / _post."""

    def _patch_client_get(self, side_effect):
        client = MagicMock()
        client.get.side_effect = side_effect
        client_cls = MagicMock()
        client_cls.return_value.__enter__.return_value = client
        return patch("arcnet.hq_tools.httpx.Client", client_cls), client

    def _patch_client_post(self, side_effect):
        client = MagicMock()
        client.post.side_effect = side_effect
        client_cls = MagicMock()
        client_cls.return_value.__enter__.return_value = client
        return patch("arcnet.hq_tools.httpx.Client", client_cls), client

    def _assert_err(self, out: dict, *, tool: str, error: str | None = None) -> None:
        self.assertIsInstance(out, dict)
        self.assertEqual(out.get("ok"), False)
        self.assertEqual(out.get("tool"), tool)
        self.assertIn("error", out)
        if error is not None:
            self.assertEqual(out.get("error"), error)

    def test_get_timeout(self) -> None:
        from arcnet import hq_tools

        p, _ = self._patch_client_get(httpx.TimeoutException("slow"))
        with p:
            out = hq_tools._get("/api/fleet", tool="fleet_overview", retries=0)
        self._assert_err(out, tool="fleet_overview", error="timeout")

    def test_get_4xx(self) -> None:
        from arcnet import hq_tools

        p, _ = self._patch_client_get(_http_status_error(404))
        with p:
            out = hq_tools._get("/api/fleet", tool="fleet_overview", retries=0)
        self._assert_err(out, tool="fleet_overview", error="http_error")
        self.assertEqual(out.get("status"), 404)

    def test_get_5xx(self) -> None:
        from arcnet import hq_tools

        p, _ = self._patch_client_get(_http_status_error(503))
        with p:
            out = hq_tools._get("/api/fleet", tool="fleet_overview", retries=0)
        self._assert_err(out, tool="fleet_overview", error="http_error")
        self.assertEqual(out.get("status"), 503)

    def test_post_timeout(self) -> None:
        from arcnet import hq_tools

        p, _ = self._patch_client_post(httpx.TimeoutException("slow"))
        with p:
            out = hq_tools._post("/api/signal", {}, tool="propose_model_change")
        self._assert_err(out, tool="propose_model_change", error="timeout")

    def test_post_4xx(self) -> None:
        from arcnet import hq_tools

        p, _ = self._patch_client_post(_http_status_error(400))
        with p:
            out = hq_tools._post("/api/signal", {}, tool="propose_model_change")
        self._assert_err(out, tool="propose_model_change", error="http_error")
        self.assertEqual(out.get("status"), 400)

    def test_post_5xx(self) -> None:
        from arcnet import hq_tools

        p, _ = self._patch_client_post(_http_status_error(500))
        with p:
            out = hq_tools._post("/api/signal", {}, tool="propose_model_change")
        self._assert_err(out, tool="propose_model_change", error="http_error")
        self.assertEqual(out.get("status"), 500)

    def test_signoz_status_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_get", return_value=_tool_err("signoz_status")):
            out = hq_tools.signoz_status()
        self._assert_err(out, tool="signoz_status")

    def test_signoz_evidence_missing_id(self) -> None:
        from arcnet import hq_tools

        out = hq_tools.signoz_evidence("")
        self._assert_err(out, tool="signoz_evidence", error="session_id required")

    def test_signoz_evidence_http_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_get", return_value=_tool_err("signoz_evidence")):
            out = hq_tools.signoz_evidence("s_x")
        self._assert_err(out, tool="signoz_evidence")

    def test_fleet_overview_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_get", return_value=_tool_err("fleet_overview")):
            out = hq_tools.fleet_overview()
        self._assert_err(out, tool="fleet_overview")

    def test_agent_signals_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "signals_view", side_effect=RuntimeError("down")
        ):
            out = hq_tools.agent_signals("agent_j")
        self._assert_err(out, tool="agent_signals", error="signals_failed")

    def test_session_check_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "check_session", side_effect=RuntimeError("down")
        ):
            out = hq_tools.session_check("s_x")
        self._assert_err(out, tool="session_check", error="check_failed")

    def test_case_file_view_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "incident_view", side_effect=RuntimeError("down")
        ):
            out = hq_tools.case_file_view("s_x")
        self._assert_err(out, tool="case_file_view", error="incident_failed")

    def test_replay_compare_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "_compare_replay_verdicts", side_effect=RuntimeError("down")
        ):
            out = hq_tools.replay_compare("s_x")
        self._assert_err(out, tool="replay_compare", error="compare_failed")

    def test_griffin_anomalies_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_get", return_value=_tool_err("griffin_anomalies")):
            out = hq_tools.griffin_anomalies()
        self._assert_err(out, tool="griffin_anomalies")

    def test_list_agent_models_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_get", return_value=_tool_err("list_agent_models")):
            out = hq_tools.list_agent_models("agent_j")
        self._assert_err(out, tool="list_agent_models")

    def test_recommend_models_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "_recommend_models", side_effect=RuntimeError("catalog blip")
        ):
            out = hq_tools.recommend_models("injection_resist")
        self._assert_err(out, tool="recommend_models", error="recommend_failed")

    def test_agent_version_timeline_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "_get", return_value=_tool_err("agent_version_timeline")
        ):
            out = hq_tools.agent_version_timeline("agent_j")
        self._assert_err(out, tool="agent_version_timeline")

    def test_register_agent_version_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "_post", return_value=_tool_err("register_agent_version")
        ):
            out = hq_tools.register_agent_version("agent_j", "v1")
        self._assert_err(out, tool="register_agent_version")

    def test_propose_model_change_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_collect_evidence_refs", return_value=["agent:agent_j"]):
            with patch.object(
                hq_tools, "_post", return_value=_tool_err("propose_model_change")
            ):
                out = hq_tools.propose_model_change("agent_j", "gpt-4o", "reason")
        self._assert_err(out, tool="propose_model_change")

    def test_list_model_proposals_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "_get", return_value=_tool_err("list_model_proposals")
        ):
            out = hq_tools.list_model_proposals(agent_id="agent_j")
        self._assert_err(out, tool="list_model_proposals")

    def test_apply_model_change_refuses_without_confirm(self) -> None:
        from arcnet import hq_tools

        out = hq_tools.apply_model_change("agent_j", "gpt-4o", "v1", confirm=False)
        self._assert_err(out, tool="apply_model_change")
        self.assertFalse(out.get("agentos_reload_required"))

    def test_apply_model_change_http_error(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools, "_post", return_value=_tool_err("apply_model_change")
        ):
            out = hq_tools.apply_model_change(
                "agent_j", "gpt-4o", "v1", confirm=True
            )
        self._assert_err(out, tool="apply_model_change")


class EvidenceRefsContractTests(unittest.TestCase):
    def test_propose_always_includes_evidence_refs(self) -> None:
        from arcnet import hq_tools

        with patch.object(hq_tools, "_collect_evidence_refs", return_value=[]):
            with patch.object(
                hq_tools,
                "_post",
                return_value={"signal_id": "sig_1", "source": "hq_agent"},
            ):
                out = hq_tools.propose_model_change("agent_j", "gpt-4o", "x")
        self.assertTrue(out.get("ok"))
        self.assertIn("evidence_refs", out)
        self.assertEqual(out["evidence_refs"], [])
        self.assertIn("evidence_refs_empty_reason", out)
        self.assertTrue(str(out["evidence_refs_empty_reason"]).strip())

    def test_propose_with_refs(self) -> None:
        from arcnet import hq_tools

        with patch.object(
            hq_tools,
            "_post",
            return_value={"signal_id": "sig_2", "source": "hq_agent"},
        ):
            out = hq_tools.propose_model_change(
                "agent_j",
                "gpt-4o",
                "x",
                evidence_refs=["replay:r1"],
            )
        self.assertEqual(out["evidence_refs"], ["replay:r1"])
        self.assertNotIn("evidence_refs_empty_reason", out)

    def test_recommend_unknown_task_has_empty_reason(self) -> None:
        from arcnet.model_explore import recommend_models

        out = recommend_models("not_a_real_task")
        self.assertEqual(out["recommendations"], [])
        self.assertIn("evidence_refs", out)
        self.assertEqual(out["evidence_refs"], [])
        self.assertTrue(str(out.get("evidence_refs_empty_reason") or "").strip())

    def test_recommend_rows_carry_evidence_refs(self) -> None:
        from arcnet.model_explore import recommend_models

        out = recommend_models("injection_resist", constraints={"live": False})
        self.assertTrue(out.get("recommendations"))
        self.assertIn("evidence_refs", out)
        self.assertTrue(out["evidence_refs"])
        for row in out["recommendations"]:
            self.assertIn("evidence_refs", row)
            self.assertIsInstance(row["evidence_refs"], list)
            self.assertTrue(row["evidence_refs"])


def _tool_err(tool: str) -> dict:
    return {"ok": False, "error": "http_error", "tool": tool, "status": 503}


if __name__ == "__main__":
    unittest.main()
