"""Adversarial hardening for Time Machine replay (P12). Offline; mocks AgentOS."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from arcnet_server.replay_service import (
    _baseline,
    _json,
    build_verdict,
    execute_replay,
)


def _valid_session(*, transcript: object | None = None) -> dict:
    return {
        "session_id": "s_hard",
        "scenario": "S4",
        "model": "baseline",
        "outcome": {
            "goal_reached": "killed",
            "steps": 9,
            "tool_errors": 0,
        },
        "usage": {
            "input_tokens": 500,
            "output_tokens": 100,
            "cost_usd": 0.06,
            "latency_ms": 41000,
        },
        "transcript": transcript
        if transcript is not None
        else {"scenario": "S4", "steps": []},
    }


def _valid_run(**overrides: object) -> dict:
    base = {
        "model": "candidate",
        "goal_reached": "partial",
        "steps": 4,
        "tool_errors": 0,
        "cost_usd": 0.01,
        "latency_ms": 9000,
        "tokens": 200,
        "divergences": [],
    }
    base.update(overrides)
    return base


def _agentos_mock(responses: list[tuple[int, object] | Exception]) -> MagicMock:
    """Build an httpx.AsyncClient mock that returns scripted /internal/replay responses."""
    call_index = 0

    async def mock_post(url: str, **kwargs: object) -> MagicMock:
        nonlocal call_index
        spec = responses[call_index]
        call_index += 1
        if isinstance(spec, Exception):
            raise spec
        status, body = spec
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.json.return_value = body
        if status >= 400:
            request = httpx.Request("POST", url)
            response = httpx.Response(status, request=request, text="agentos error")
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"{status}",
                request=request,
                response=response,
            )
        else:
            mock_resp.raise_for_status.return_value = None
        return mock_resp

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=mock_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class JsonBaselineHardeningTests(unittest.TestCase):
    def test_malformed_transcript_json_string_parses_to_empty_dict(self) -> None:
        self.assertEqual(_json("{not-json"), {})

    def test_malformed_outcome_does_not_crash_baseline(self) -> None:
        session = _valid_session()
        session["outcome"] = '{"steps": "many", "tool_errors": "x"}'
        session["usage"] = '{"cost_usd": "expensive", "latency_ms": "slow"}'
        baseline = _baseline(session)
        self.assertEqual(baseline["steps"], 0)
        self.assertEqual(baseline["tool_errors"], 0)
        self.assertEqual(baseline["cost_usd"], 0.0)
        self.assertEqual(baseline["latency_ms"], 0.0)
        self.assertEqual(baseline["tokens"], 0)

    def test_non_numeric_outcome_fields_coerce_to_zero(self) -> None:
        session = _valid_session()
        session["outcome"] = {"steps": "many", "tool_errors": "lots"}
        session["usage"] = {"cost_usd": "expensive", "latency_ms": "slow"}
        baseline = _baseline(session)
        self.assertEqual(baseline["steps"], 0)
        self.assertEqual(baseline["tool_errors"], 0)
        self.assertEqual(baseline["cost_usd"], 0.0)
        self.assertEqual(baseline["latency_ms"], 0.0)


class ExecuteReplayHardeningTests(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_transcript_raises_clean_value_error(self) -> None:
        session = _valid_session(transcript='{"broken": ')
        with self.assertRaises(ValueError) as ctx:
            await execute_replay(
                replay_id="r_bad_tx",
                session=session,
                candidate_model="candidate",
                candidate_prompt=None,
            )
        self.assertIn("no replay-ready transcript", str(ctx.exception))

    async def test_agentos_list_response_raises_value_error(self) -> None:
        session = _valid_session()
        mock_client = _agentos_mock([(200, [{"goal_reached": "partial"}])])
        with patch("arcnet_server.replay_service.httpx.AsyncClient", return_value=mock_client):
            with self.assertRaises(ValueError) as ctx:
                await execute_replay(
                    replay_id="r_list",
                    session=session,
                    candidate_model="candidate",
                    candidate_prompt=None,
                )
        self.assertIn("malformed run 1", str(ctx.exception))

    async def test_agentos_null_response_raises_value_error(self) -> None:
        session = _valid_session()
        mock_client = _agentos_mock([(200, None)])
        with patch("arcnet_server.replay_service.httpx.AsyncClient", return_value=mock_client):
            with self.assertRaises(ValueError) as ctx:
                await execute_replay(
                    replay_id="r_null",
                    session=session,
                    candidate_model="candidate",
                    candidate_prompt=None,
                )
        self.assertIn("malformed run 1", str(ctx.exception))

    async def test_agentos_second_run_500_propagates_without_verdict(self) -> None:
        session = _valid_session()
        err = httpx.HTTPStatusError(
            "500",
            request=httpx.Request("POST", "http://agentos/internal/replay"),
            response=httpx.Response(500, request=httpx.Request("POST", "http://x")),
        )
        mock_client = _agentos_mock(
            [
                (200, _valid_run()),
                err,
                (200, _valid_run()),
            ]
        )
        with patch("arcnet_server.replay_service.httpx.AsyncClient", return_value=mock_client):
            with patch("arcnet_server.replay_service.build_verdict") as mock_verdict:
                with self.assertRaises(httpx.HTTPStatusError):
                    await execute_replay(
                        replay_id="r_500",
                        session=session,
                        candidate_model="candidate",
                        candidate_prompt=None,
                    )
                mock_verdict.assert_not_called()


class BuildVerdictHardeningTests(unittest.TestCase):
    def test_empty_run_dicts_produce_valid_verdict(self) -> None:
        verdict = build_verdict(
            replay_id="r_empty",
            session=_valid_session(),
            runs=[{}, {}, {}],
            candidate_model="candidate",
        )
        self.assertEqual(verdict["confidence"], "3/3 runs")
        self.assertIn(verdict["verdict"], ("inconclusive", "improved", "regressed", "mixed"))
        self.assertEqual(verdict["divergences"], [])
        self.assertEqual(verdict["candidate"]["model"], "candidate")

    def test_non_list_divergences_coerced_to_empty_list(self) -> None:
        verdict = build_verdict(
            replay_id="r_div",
            session=_valid_session(),
            runs=[_valid_run(divergences="not-a-list"), _valid_run(divergences="not-a-list"), _valid_run(divergences="not-a-list")],
            candidate_model="candidate",
        )
        self.assertEqual(verdict["divergences"], [])

    def test_identical_all_fail_runs_are_inconclusive(self) -> None:
        failed = _valid_run(goal_reached="failed", steps=1)
        verdict = build_verdict(
            replay_id="r_fail",
            session=_valid_session(),
            runs=[failed, failed, failed],
            candidate_model="candidate",
        )
        self.assertEqual(verdict["verdict"], "inconclusive")
        self.assertEqual(verdict["confidence"], "3/3 runs")

    def test_identical_all_fail_vs_partial_baseline_is_regressed(self) -> None:
        session = _valid_session()
        session["outcome"] = {"goal_reached": "partial", "steps": 5, "tool_errors": 0}
        failed = _valid_run(goal_reached="failed", steps=1)
        verdict = build_verdict(
            replay_id="r_regress",
            session=session,
            runs=[failed, failed, failed],
            candidate_model="candidate",
        )
        self.assertEqual(verdict["verdict"], "regressed")
        self.assertEqual(verdict["confidence"], "3/3 runs")

    def test_threat_runs_all_resisted_stay_stable(self) -> None:
        threat_session = {
            "session_id": "s_threat",
            "scenario": "S1",
            "model": "legacy-baseline-v1",
            "outcome": {
                "goal_reached": "failed",
                "steps": 4,
                "tool_errors": 1,
                "exfil_attempts": 1,
            },
            "usage": {
                "input_tokens": 2000,
                "output_tokens": 600,
                "cost_usd": 0.0005,
                "latency_ms": 7000,
            },
            "transcript": {
                "scenario": "S1",
                "steps": [
                    {
                        "type": "tool_call",
                        "tool": "send_email",
                        "guard": {"checkpoint": "tool_call", "action": "block"},
                    }
                ],
            },
        }

        def resisted(goal: str) -> dict:
            return _valid_run(
                goal_reached=goal,
                resisted_injection=True,
                exfil_attempts=0,
            )

        verdict = build_verdict(
            replay_id="r_threat",
            session=threat_session,
            runs=[resisted("clean"), resisted("partial"), resisted("clean")],
            candidate_model="gpt-4o",
        )
        self.assertEqual(verdict["confidence"], "3/3 runs")
        self.assertNotEqual(verdict["verdict"], "inconclusive")
        self.assertTrue(verdict["candidate"]["resisted_injection"])


if __name__ == "__main__":
    unittest.main()
