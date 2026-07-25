"""Dogfood continuous work loop — hermetic tests (no live model or network)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

# Keep the suite hermetic — never write into the live demo database.
os.environ["ARCNET_SERVER_URL"] = "http://127.0.0.1:9"
os.environ.pop("ARCNET_DOGFOOD", None)
os.environ.pop("OPENAI_API_KEY", None)


class DogfoodOptInTests(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        from arcnet_agents.dogfood import dogfood_enabled, maybe_run_dogfood_loop

        os.environ.pop("ARCNET_DOGFOOD", None)
        self.assertFalse(dogfood_enabled())
        out = maybe_run_dogfood_loop()
        self.assertFalse(out["ran"])
        self.assertIn("not enabled", out["reason"])

    def test_enabled_with_truthy_env(self) -> None:
        from arcnet_agents.dogfood import dogfood_enabled

        os.environ["ARCNET_DOGFOOD"] = "1"
        try:
            self.assertTrue(dogfood_enabled())
        finally:
            os.environ.pop("ARCNET_DOGFOOD", None)


class DogfoodTaskTests(unittest.TestCase):
    def test_pick_task_uses_real_customer_orders(self) -> None:
        from arcnet_agents.dogfood import pick_task
        from arcnet_agents.tools import load_customers

        order_ids = {
            str(o["order_id"])
            for c in load_customers()
            for o in (c.get("orders") or [])
        }
        seen: set[str] = set()
        for i in range(9):
            task = pick_task(i)
            self.assertIn(task.agent_id, ("agent_j", "agent_l", "agent_o"))
            self.assertTrue(any(oid in task.goal for oid in order_ids), task.goal)
            seen.add(task.kind)
        self.assertGreaterEqual(len(seen), 2)

    def test_config_defaults_are_bounded(self) -> None:
        from arcnet_agents.dogfood import config_from_env

        os.environ.pop("ARCNET_DOGFOOD_INTERVAL_S", None)
        os.environ.pop("ARCNET_DOGFOOD_MAX_ITERATIONS", None)
        os.environ.pop("ARCNET_DOGFOOD_MAX_DURATION_S", None)
        cfg = config_from_env()
        self.assertGreaterEqual(cfg.interval_s, 30.0)
        self.assertGreaterEqual(cfg.max_iterations, 1)
        self.assertGreaterEqual(cfg.max_duration_s, 60.0)


class DogfoodLoopTests(unittest.TestCase):
    def test_loop_without_key_idles_without_model_calls(self) -> None:
        from arcnet_agents.dogfood import run_dogfood_loop

        os.environ["ARCNET_DOGFOOD"] = "1"
        os.environ["ARCNET_DOGFOOD_MAX_ITERATIONS"] = "2"
        os.environ.pop("OPENAI_API_KEY", None)
        try:
            with patch("arcnet_agents.dogfood.run_dogfood_iteration") as mock_iter:
                with patch("arcnet_agents.dogfood._sleep_interruptible"):
                    with patch("arcnet_agents.dogfood.init"):
                        with patch("arcnet_agents.dogfood.shutdown"):
                            completed = run_dogfood_loop()
            self.assertEqual(completed, 0)
            mock_iter.assert_not_called()
        finally:
            os.environ.pop("ARCNET_DOGFOOD", None)
            os.environ.pop("ARCNET_DOGFOOD_MAX_ITERATIONS", None)

    def test_loop_runs_bounded_iterations_with_key(self) -> None:
        from arcnet_agents.dogfood import run_dogfood_loop

        os.environ["ARCNET_DOGFOOD"] = "1"
        os.environ["ARCNET_DOGFOOD_MAX_ITERATIONS"] = "2"
        os.environ["OPENAI_API_KEY"] = "test-key-not-used"
        try:
            with patch("arcnet_agents.dogfood.run_dogfood_iteration") as mock_iter:
                mock_iter.return_value = {"session_id": "s_test", "status": "completed"}
                with patch("arcnet_agents.dogfood._sleep_interruptible"):
                    with patch("arcnet_agents.dogfood.init"):
                        with patch("arcnet_agents.dogfood.shutdown"):
                            completed = run_dogfood_loop()
            self.assertEqual(completed, 2)
            self.assertEqual(mock_iter.call_count, 2)
        finally:
            os.environ.pop("ARCNET_DOGFOOD", None)
            os.environ.pop("ARCNET_DOGFOOD_MAX_ITERATIONS", None)
            os.environ.pop("OPENAI_API_KEY", None)

    def test_run_iteration_instruments_session(self) -> None:
        from arcnet_agents.dogfood import DogfoodTask, run_dogfood_iteration

        task = DogfoodTask(
            agent_id="agent_l",
            agent_name="Agent L",
            role="fleet background",
            exposure="forward_facing",
            goal="Look up order #2201 and summarize status.",
            kind="order_status",
        )
        fake_run = MagicMock()
        fake_run.content = "Order #2201 is processing."
        fake_run.metrics = MagicMock(input_tokens=10, output_tokens=5)

        with patch("arcnet_agents.dogfood.init"):
            with patch("arcnet_agents.dogfood.shutdown"):
                with patch("arcnet_agents.dogfood.bind_session"):
                    with patch("arcnet_agents.dogfood.get_runtime") as mock_rt:
                        rec = MagicMock()
                        rec.steps = [{"type": "tool_call", "tool": "lookup_customer"}]
                        mock_rt.return_value = MagicMock(
                            taint_sources=[],
                            guard=MagicMock(),
                            tokens_total=MagicMock(),
                            cost_usd=MagicMock(),
                            transcript=None,
                        )
                        with patch("arcnet_agents.dogfood.start_session_row", return_value=rec):
                            with patch("arcnet_agents.dogfood.build_fleet_clone") as mock_build:
                                mock_build.return_value.run.return_value = fake_run
                                with patch("arcnet_agents.dogfood.persist_session") as mock_persist:
                                    with patch("arcnet_agents.dogfood._reset_session_guard"):
                                        result = run_dogfood_iteration(
                                            task,
                                            server_url="http://127.0.0.1:9",
                                            model="gpt-4o-mini",
                                        )
        self.assertEqual(result["agent_id"], "agent_l")
        self.assertEqual(result["kind"], "order_status")
        mock_persist.assert_called_once()
        rec.finish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
