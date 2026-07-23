"""TabFM worker — forecast contract for Griffin (P7-A stub → P7-B wire).

Interface lock:
  forecast(history, features) -> predictions

Heavy TabFM load/fit stays lazy until ``backend="tabfm"`` is requested.
MAD fallback reuses ``griffin.mad_judge`` (no duplicated MAD math).
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Sequence

from arcnet_server.griffin import mad_judge

logger = logging.getLogger("arcnet.tabfm")

# Honesty pins
WORKER_STATUS = "ready"
ESTIMATOR_WHEN_LIVE = "tabfm"
ESTIMATOR_FALLBACK = "mad"

ERROR_TABFM_UNAVAILABLE = "tabfm_unavailable"
ERROR_TABFM_NOT_WIRED = ERROR_TABFM_UNAVAILABLE  # P7-A alias for tests

CHECKPOINT = "google/tabfm-1.0.0-pytorch"
SUBFOLDER = "regression"

_MODEL_LOCK = threading.Lock()
_MODEL_LOADED = False
_MODEL: Any = None

# Test hook — inject fake TabFM backend without downloading weights.
_FORECAST_OVERRIDE: Callable[[Sequence[float], Sequence[Sequence[float]] | None], dict[str, Any]] | None = (
    None
)


def set_forecast_override(
    fn: Callable[[Sequence[float], Sequence[Sequence[float]] | None], dict[str, Any]] | None,
) -> None:
    """Replace TabFM inference for tests (None restores default)."""
    global _FORECAST_OVERRIDE
    _FORECAST_OVERRIDE = fn


def _build_features(history: Sequence[float]) -> list[list[float]]:
    """Feature matrix aligned with history (matches phase7 spike)."""
    n = len(history)
    if n == 0:
        return []
    rows: list[list[float]] = []
    for i in range(n):
        t = float(i)
        y = float(history[i])
        window = [float(history[j]) for j in range(max(0, i - 4), i + 1)]
        roll_mean = sum(window) / len(window)
        roll_std = (
            (sum((v - roll_mean) ** 2 for v in window) / len(window)) ** 0.5 if len(window) > 1 else 0.0
        )
        lag1 = float(history[i - 1]) if i > 0 else y
        rows.append([t, t % 60.0, roll_mean, roll_std, lag1])
    return rows


def _load_tabfm_model() -> Any:
    """Lazy, once-per-process TabFM weight load (thread-safe)."""
    global _MODEL, _MODEL_LOADED
    with _MODEL_LOCK:
        if _MODEL_LOADED:
            return _MODEL
        import safetensors  # noqa: F401 — required by HF safetensors path
        from tabfm import tabfm_v1_0_0_pytorch as tabfm_v1_0_0

        try:
            model = tabfm_v1_0_0.load(model_type=SUBFOLDER)
        except TypeError:
            model = tabfm_v1_0_0.load()
        _MODEL = model
        _MODEL_LOADED = True
        return _MODEL


def _tabfm_predict(history: Sequence[float], features: Sequence[Sequence[float]] | None) -> dict[str, Any]:
    """Run TabFM fit+predict on history tail; returns structured success or error."""
    if _FORECAST_OVERRIDE is not None:
        return _FORECAST_OVERRIDE(history, features)

    hist = [float(x) for x in history]
    if len(hist) < 30:
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": "tabfm",
            "status": "warming",
            "detail": {"error": "short_history", "n": len(hist), "worker_status": WORKER_STATUS},
        }

    try:
        import numpy as np
        from tabfm import TabFMRegressor
    except ImportError as exc:
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": "tabfm",
            "status": "error",
            "detail": {
                "error": ERROR_TABFM_UNAVAILABLE,
                "alias": ERROR_TABFM_NOT_WIRED,
                "worker_status": WORKER_STATUS,
                "message": f"tabfm/torch not installed: {exc}",
            },
        }

    feat_rows = list(features) if features is not None else _build_features(hist)
    if len(feat_rows) != len(hist):
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": "tabfm",
            "status": "error",
            "detail": {
                "error": ERROR_TABFM_UNAVAILABLE,
                "message": "features length mismatch",
                "worker_status": WORKER_STATUS,
            },
        }

    hold = min(20, max(1, len(hist) // 3))
    if len(hist) <= hold + 1:
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": "tabfm",
            "status": "warming",
            "detail": {"error": "short_history", "n": len(hist)},
        }

    try:
        model = _load_tabfm_model()
    except Exception as exc:  # noqa: BLE001
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": "tabfm",
            "status": "error",
            "detail": {
                "error": ERROR_TABFM_UNAVAILABLE,
                "alias": ERROR_TABFM_NOT_WIRED,
                "worker_status": WORKER_STATUS,
                "message": f"model load failed: {exc}",
            },
        }

    x_arr = np.asarray(feat_rows, dtype=np.float64)
    y_arr = np.asarray(hist, dtype=np.float64)
    x_train, y_train = x_arr[:-hold], y_arr[:-hold]
    x_pred = x_arr[-1:]

    try:
        reg = TabFMRegressor(model=model)
        reg.fit(x_train, y_train)
        pred = reg.predict(x_pred)
        pred_val = float(np.asarray(pred).ravel()[0])
    except Exception as exc:  # noqa: BLE001
        return {
            "predictions": [],
            "estimator": ESTIMATOR_FALLBACK,
            "backend": "tabfm",
            "status": "error",
            "detail": {
                "error": ERROR_TABFM_UNAVAILABLE,
                "worker_status": WORKER_STATUS,
                "message": f"fit/predict failed: {exc}",
            },
        }

    judged = mad_judge(hist, observed=hist[-1])
    detail = {**judged, "tabfm_point": pred_val}
    return {
        "predictions": [pred_val],
        "estimator": ESTIMATOR_WHEN_LIVE,
        "backend": "tabfm",
        "status": "ready",
        "detail": detail,
        "worker_status": WORKER_STATUS,
    }


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
        Optional per-row feature matrix aligned with history. Built from
        history when omitted (TabFM path).
    backend:
        ``mad_fallback`` (default) or ``tabfm`` (lazy TabFM inference).

    Returns
    -------
    dict with keys:
      predictions: list[float]  — point forecast(s)
      estimator: str            — ``mad`` or ``tabfm`` when live
      backend: str
      status: str               — warming | ready | error
      detail: dict              — mad_judge payload or error
    """
    hist = [float(x) for x in history]

    if backend == "tabfm":
        return _tabfm_predict(hist, features)

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
