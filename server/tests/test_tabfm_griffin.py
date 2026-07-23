"""P7-B — TabFM Griffin worker: honest status, MAD degrade, opt-in env."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arcnet_server.tabfm_worker import ERROR_TABFM_UNAVAILABLE, set_forecast_override

ROOT = Path(__file__).resolve().parents[2]


def _seed_series(path: Path, n: int = 40) -> None:
    pts = [{"t": float(i), "v": 100.0 + 0.2 * i} for i in range(n)]
    data = {"arcnet.tokens.total|agent_j": pts}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _reset_tabfm_state() -> None:
    import arcnet_server.griffin as g

    g.reset_tabfm_state_for_tests()
    g._CACHE.clear()
    g._CACHE.update(
        {
            "model": "mad",
            "estimator": "mad",
            "status": "cold",
            "series": {},
            "proxy_series": {},
            "series_source": None,
            "last_cycle_ms": None,
            "last_evaluate_ms": None,
            "last_anomaly": None,
            "anomalies": [],
        }
    )


class TabfmGriffinTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_tabfm_state()
        set_forecast_override(None)

    def tearDown(self) -> None:
        set_forecast_override(None)
        os.environ.pop("ARCNET_TABFM", None)
        os.environ.pop("ARCNET_GRIFFIN_SERIES", None)

    def test_disabled_by_default_status_mad(self) -> None:
        import arcnet_server.griffin as g

        os.environ.pop("ARCNET_TABFM", None)
        self.assertFalse(g.tabfm_enabled())
        snap = g.cache_snapshot()
        self.assertEqual(snap["estimator"], "mad")
        self.assertIn("tabfm", snap)
        self.assertFalse(snap["tabfm"]["enabled"])
        self.assertIsNone(snap["tabfm"]["degrade_reason"])

    def test_no_tabfm_package_import_when_disabled(self) -> None:
        env = os.environ.copy()
        env.pop("ARCNET_TABFM", None)
        env["PYTHONPATH"] = f"{ROOT / 'sdk'}:{ROOT / 'server'}"
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import os; os.environ.pop('ARCNET_TABFM', None); "
                    "import arcnet_server.griffin as g; "
                    "g.start_tabfm_worker(lambda: None); "
                    "import sys; print('tabfm' in sys.modules)"
                ),
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "False")

    def test_worker_success_flips_estimator_honestly(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp:
            series_path = Path(tmp) / "griffin_series.json"
            _seed_series(series_path)
            os.environ["ARCNET_TABFM"] = "1"
            os.environ["ARCNET_GRIFFIN_SERIES"] = str(series_path)

            def _fake_tabfm(history, features):  # noqa: ANN001
                return {
                    "predictions": [float(history[-1]) + 1.0],
                    "estimator": "tabfm",
                    "backend": "tabfm",
                    "status": "ready",
                    "detail": {},
                }

            set_forecast_override(_fake_tabfm)
            snap_before = g.cache_snapshot()
            self.assertEqual(snap_before["estimator"], "mad")

            g.run_tabfm_cycle_once(m.get_conn)

            snap_after = g.cache_snapshot()
            self.assertEqual(snap_after["estimator"], "tabfm")
            self.assertEqual(snap_after["model"], "tabfm")
            self.assertTrue(snap_after["tabfm"]["enabled"])
            self.assertTrue(snap_after["tabfm"]["loaded"])
            self.assertIsNotNone(snap_after["tabfm"]["last_forecast_ms"])
            self.assertIsNone(snap_after["tabfm"]["degrade_reason"])

    def test_forecast_error_degrades_to_mad(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp:
            series_path = Path(tmp) / "griffin_series.json"
            _seed_series(series_path)
            os.environ["ARCNET_TABFM"] = "1"
            os.environ["ARCNET_GRIFFIN_SERIES"] = str(series_path)

            def _fail_tabfm(history, features):  # noqa: ANN001
                return {
                    "predictions": [],
                    "estimator": "mad",
                    "backend": "tabfm",
                    "status": "error",
                    "detail": {"error": ERROR_TABFM_UNAVAILABLE, "message": "missing weights"},
                }

            set_forecast_override(_fail_tabfm)
            g.run_tabfm_cycle_once(m.get_conn)
            g.run_tabfm_cycle_once(m.get_conn)

            snap = g.cache_snapshot()
            self.assertEqual(snap["estimator"], "mad")
            self.assertTrue(g._TABFM_STATE["degraded"])
            self.assertEqual(snap["tabfm"]["degrade_reason"], ERROR_TABFM_UNAVAILABLE)

    def test_exception_degrades_to_mad(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp:
            series_path = Path(tmp) / "griffin_series.json"
            _seed_series(series_path)
            os.environ["ARCNET_TABFM"] = "1"
            os.environ["ARCNET_GRIFFIN_SERIES"] = str(series_path)

            def _boom(history, features):  # noqa: ANN001
                raise RuntimeError("boom")

            set_forecast_override(_boom)
            g.run_tabfm_cycle_once(m.get_conn)

            snap = g.cache_snapshot()
            self.assertEqual(snap["estimator"], "mad")
            self.assertIn("boom", snap["tabfm"]["degrade_reason"] or "")

    def test_status_endpoint_tabfm_fields(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "t.db"
            series_path = Path(tmp) / "griffin_series.json"
            _seed_series(series_path)
            with patch.dict(
                os.environ,
                {
                    "ARCNET_DB_PATH": str(db_path),
                    "ARCNET_TABFM": "1",
                    "ARCNET_GRIFFIN_SERIES": str(series_path),
                },
                clear=False,
            ):
                from fastapi.testclient import TestClient

                import arcnet_server.main as main_mod

                main_mod.get_conn()

                def _fake_tabfm(history, features):  # noqa: ANN001
                    return {
                        "predictions": [123.45],
                        "estimator": "tabfm",
                        "backend": "tabfm",
                        "status": "ready",
                        "detail": {},
                    }

                set_forecast_override(_fake_tabfm)
                g.run_tabfm_cycle_once(m.get_conn)

                with TestClient(main_mod.app) as client:
                    body = client.get("/api/griffin/status").json()
                self.assertEqual(body["estimator"], "tabfm")
                self.assertIn("tabfm", body)
                self.assertIsNotNone(body["tabfm"]["last_forecast_ms"])


if __name__ == "__main__":
    unittest.main()
