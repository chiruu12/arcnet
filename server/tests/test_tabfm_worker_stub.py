"""P7-A — TabFM worker stub MAD fallback (not wired to runtime)."""

from __future__ import annotations

import unittest

from arcnet_server.tabfm_worker import (
    ERROR_TABFM_UNAVAILABLE,
    ESTIMATOR_FALLBACK,
    WORKER_STATUS,
    forecast,
    mad_fallback_forecast,
)


def _synthetic_series(n: int = 40, base: float = 100.0) -> list[float]:
    # Gentle drift + small noise — MAD forecast should stay near base+drift/2.
    return [base + 0.2 * i + ((-1) ** i) * 0.5 for i in range(n)]


class TabfmWorkerStubTests(unittest.TestCase):
    def test_mad_fallback_ready_on_warm_series(self) -> None:
        hist = _synthetic_series(40)
        out = mad_fallback_forecast(hist)
        self.assertEqual(out["estimator"], ESTIMATOR_FALLBACK)
        self.assertEqual(out["estimator"], "mad")
        self.assertEqual(out["backend"], "mad_fallback")
        self.assertEqual(out["worker_status"], WORKER_STATUS)
        self.assertEqual(out["status"], "ready")
        self.assertEqual(len(out["predictions"]), 1)
        pred = out["predictions"][0]
        self.assertIsInstance(pred, float)
        # Sane: within the series range expanded by a small margin
        lo, hi = min(hist), max(hist)
        margin = max(5.0, 0.25 * (hi - lo))
        self.assertGreaterEqual(pred, lo - margin)
        self.assertLessEqual(pred, hi + margin)
        detail = out["detail"]
        self.assertIn("band_lo", detail)
        self.assertIn("band_hi", detail)
        self.assertFalse(detail.get("outlier"))

    def test_forecast_default_is_mad_fallback(self) -> None:
        hist = _synthetic_series(35)
        out = forecast(hist, features=None)
        self.assertEqual(out["estimator"], "mad")
        self.assertEqual(out["status"], "ready")
        self.assertTrue(out["predictions"])

    def test_warming_on_short_history(self) -> None:
        out = forecast([1.0, 2.0, 3.0])
        self.assertEqual(out["status"], "warming")
        self.assertEqual(out["predictions"], [])
        self.assertEqual(out["estimator"], "mad")

    def test_tabfm_backend_unavailable_without_weights(self) -> None:
        out = forecast(_synthetic_series(40), backend="tabfm")
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["estimator"], "mad")
        self.assertEqual(out["detail"].get("error"), ERROR_TABFM_UNAVAILABLE)
        self.assertEqual(out["predictions"], [])

    def test_empty_history(self) -> None:
        out = forecast([])
        self.assertEqual(out["status"], "warming")
        self.assertEqual(out["predictions"], [])


if __name__ == "__main__":
    unittest.main()
