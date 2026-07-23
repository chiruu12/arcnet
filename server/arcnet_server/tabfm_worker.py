"""TabFM worker contract stub (P7-A) — NOT wired to Griffin runtime.

Interface lock for P7-B:
  forecast(history, features) -> predictions

Heavy TabFM load/fit stays out of process until P7-B. This module only:
  - documents the callable boundary
  - provides a working MAD fallback via griffin.mad_judge (no duplicated MAD math)
  - must never set HQ/runtime estimator labels to tabfm

Anti-scope: do not import this from griffin cycle paths in P7-A.
"""

from __future__ import annotations

from typing import Any, Sequence

from arcnet_server.griffin import mad_judge

# Honesty pin — stub is never a live TabFM path.
WORKER_STATUS = "stub_not_wired"
ESTIMATOR_WHEN_LIVE = "tabfm"  # P7-B only, when worker healthy
ESTIMATOR_FALLBACK = "mad"


def forecast(
    history: Sequence[float],
    features: Sequence[Sequence[float]] | None = None,
    *,
    backend: str = "mad_fallback",
) -> dict[str, Any]:
    """Point-forecast contract for Griffin's estimator slot.

    Parameters
    ----------
    history:
        Metric values (oldest → newest). Last point is treated as observed
        when judging; forecast is over the series distribution.
    features:
        Optional per-row feature matrix aligned with history. Ignored by the
        MAD fallback; reserved for TabFM fit/predict in P7-B.
    backend:
        ``mad_fallback`` (default, only implemented path) or ``tabfm``
        (raises — not wired in P7-A).

    Returns
    -------
    dict with keys:
      predictions: list[float]  — point forecast(s)
      estimator: str            — ``mad`` for fallback; never claim tabfm live
      backend: str
      status: str               — warming | ready | error
      detail: dict              — mad_judge payload or error
    """
    _ = features  # reserved for TabFM feature matrix in P7-B
    hist = [float(x) for x in history]

    if backend == "tabfm":
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": "tabfm",
            "status": "error",
            "detail": {
                "error": "tabfm_not_wired",
                "worker_status": WORKER_STATUS,
                "message": "P7-A stub only; TabFM path ships in P7-B",
            },
        }

    if backend != "mad_fallback":
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": backend,
            "status": "error",
            "detail": {"error": "unknown_backend", "worker_status": WORKER_STATUS},
        }

    if not hist:
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": "mad_fallback",
            "status": "warming",
            "detail": {"error": "empty_history", "n": 0},
        }

    judged = mad_judge(hist, observed=hist[-1])
    forecast_val = judged.get("forecast")
    predictions: list[float] = []
    if forecast_val is not None:
        predictions = [float(forecast_val)]

    return {
        "predictions": predictions,
        "estimator": ESTIMATOR_FALLBACK,
        "backend": "mad_fallback",
        "status": str(judged.get("status") or "error"),
        "detail": judged,
        "worker_status": WORKER_STATUS,
    }


def mad_fallback_forecast(history: Sequence[float]) -> dict[str, Any]:
    """Explicit MAD fallback entrypoint (same as forecast(..., backend=mad_fallback))."""
    return forecast(history, features=None, backend="mad_fallback")
