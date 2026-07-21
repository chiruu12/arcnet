from __future__ import annotations

import unittest

from arcnet_server.replay_service import build_verdict


def session() -> dict:
    return {
        "session_id": "s_test",
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
        "transcript": {"scenario": "S4", "steps": []},
    }


def run(goal: str = "partial", steps: int = 4) -> dict:
    return {
        "model": "candidate",
        "goal_reached": goal,
        "steps": steps,
        "tool_errors": 0,
        "cost_usd": 0.01,
        "latency_ms": 9000,
        "tokens": 200,
        "divergences": [{"step": steps, "note": "candidate stopped"}],
    }


class VerdictTests(unittest.TestCase):
    def test_stable_improvement(self) -> None:
        verdict = build_verdict(
            replay_id="r_test",
            session=session(),
            runs=[run(), run(), run()],
            candidate_model="candidate",
        )

        self.assertEqual(verdict["verdict"], "improved")
        self.assertEqual(verdict["confidence"], "3/3 runs")
        self.assertEqual(verdict["candidate"]["goal_reached"], "partial")

    def test_behavioral_disagreement_is_inconclusive(self) -> None:
        verdict = build_verdict(
            replay_id="r_test",
            session=session(),
            runs=[run(), run(), run(goal="failed", steps=9)],
            candidate_model="candidate",
        )

        self.assertEqual(verdict["verdict"], "inconclusive")
        self.assertEqual(verdict["confidence"], "2/3 runs")

    def test_fast_failure_is_not_an_improvement(self) -> None:
        failed = run(goal="failed", steps=1)
        verdict = build_verdict(
            replay_id="r_test",
            session=session(),
            runs=[failed, failed, failed],
            candidate_model="candidate",
        )

        self.assertEqual(verdict["verdict"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
