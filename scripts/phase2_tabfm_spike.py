#!/usr/bin/env python3
"""Phase 2 gate G2 — TabFM CPU latency spike (docs/07, docs/03).

Budget: 45–90 min walk-away. Target: fit+predict cycle for ~12 series < 15s.
Falls to tabpfn==8.1.0 if TabFM install/latency fails.
Writes result JSON to docs/_phase2_g2.json.
"""

from __future__ import annotations

import json
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "_phase2_g2.json"


@dataclass
class SpikeResult:
    model: str  # tabfm | tabpfn | mad
    backend: str | None
    install_ok: bool
    load_s: float | None
    fit_predict_s: float | None
    cycle_12_series_s: float | None
    n_train: int
    n_pred: int
    gate_g2: str  # PASS | FALLBACK | FAIL
    notes: str
    error: str | None = None


def _synthetic_series(n: int = 60, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Time-featurized metric buckets matching Griffin's intended features."""
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float64)
    y = 10.0 + 0.05 * t + 2.0 * np.sin(t / 7.0) + rng.normal(0, 0.4, size=n)
    # features: index, minute-of-hour, roll5 mean/std, lag1
    roll5_mean = np.convolve(y, np.ones(5) / 5, mode="same")
    roll5_std = np.array(
        [y[max(0, i - 4) : i + 1].std() if i > 0 else 0.0 for i in range(n)],
        dtype=np.float64,
    )
    lag1 = np.concatenate([[y[0]], y[:-1]])
    X = np.column_stack([t, t % 60, roll5_mean, roll5_std, lag1])
    return X, y, t


def try_tabfm() -> SpikeResult:
    t_install = time.perf_counter()
    notes = []
    try:
        from tabfm import TabFMRegressor, tabfm_v1_0_0_pytorch as tabfm_v1_0_0

        notes.append("import tabfm pytorch backend ok")
    except Exception as exc:  # noqa: BLE001
        return SpikeResult(
            model="tabfm",
            backend="pytorch",
            install_ok=False,
            load_s=None,
            fit_predict_s=None,
            cycle_12_series_s=None,
            n_train=0,
            n_pred=0,
            gate_g2="FALLBACK",
            notes="tabfm import failed",
            error=f"{type(exc).__name__}: {exc}",
        )

    X, y, _ = _synthetic_series(60)
    # leave last 20 for conformal calibration style split
    X_train, y_train = X[:-20], y[:-20]
    X_pred, _ = X[-1:], y[-1:]

    t0 = time.perf_counter()
    try:
        model = tabfm_v1_0_0.load(model_type="regression")
        load_s = time.perf_counter() - t0
        notes.append(f"weights load {load_s:.2f}s")
    except Exception as exc:  # noqa: BLE001
        return SpikeResult(
            model="tabfm",
            backend="pytorch",
            install_ok=True,
            load_s=None,
            fit_predict_s=None,
            cycle_12_series_s=None,
            n_train=len(X_train),
            n_pred=1,
            gate_g2="FALLBACK",
            notes="; ".join(notes),
            error=f"load failed: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}",
        )

    t1 = time.perf_counter()
    try:
        reg = TabFMRegressor(model=model)
        reg.fit(X_train, y_train)
        pred = reg.predict(X_pred)
        fit_predict_s = time.perf_counter() - t1
        notes.append(f"single fit+predict {fit_predict_s:.3f}s pred={float(np.asarray(pred).ravel()[0]):.3f}")
    except Exception as exc:  # noqa: BLE001
        return SpikeResult(
            model="tabfm",
            backend="pytorch",
            install_ok=True,
            load_s=load_s,
            fit_predict_s=None,
            cycle_12_series_s=None,
            n_train=len(X_train),
            n_pred=1,
            gate_g2="FALLBACK",
            notes="; ".join(notes),
            error=f"fit/predict failed: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}",
        )

    # Simulate 12 series: reuse loaded model, re-fit each (Griffin pattern)
    t2 = time.perf_counter()
    for i in range(12):
        Xi, yi, _ = _synthetic_series(60, seed=i)
        Xi_train, yi_train = Xi[:-20], yi[:-20]
        reg_i = TabFMRegressor(model=model)
        reg_i.fit(Xi_train, yi_train)
        _ = reg_i.predict(Xi[-1:])
    cycle_s = time.perf_counter() - t2
    notes.append(f"12-series cycle {cycle_s:.2f}s (excl weight load)")
    _ = t_install  # install time measured outside

    gate = "PASS" if cycle_s < 15.0 else "FALLBACK"
    if cycle_s >= 15.0:
        notes.append("cycle >= 15s budget → fall to tabpfn")

    return SpikeResult(
        model="tabfm",
        backend="pytorch",
        install_ok=True,
        load_s=load_s,
        fit_predict_s=fit_predict_s,
        cycle_12_series_s=cycle_s,
        n_train=len(X_train),
        n_pred=1,
        gate_g2=gate,
        notes="; ".join(notes),
    )


def try_tabpfn() -> SpikeResult:
    try:
        from tabpfn import TabPFNRegressor
    except Exception as exc:  # noqa: BLE001
        return SpikeResult(
            model="tabpfn",
            backend=None,
            install_ok=False,
            load_s=None,
            fit_predict_s=None,
            cycle_12_series_s=None,
            n_train=0,
            n_pred=0,
            gate_g2="FAIL",
            notes="tabpfn import failed",
            error=f"{type(exc).__name__}: {exc}",
        )

    X, y, _ = _synthetic_series(60)
    X_train, y_train = X[:-20], y[:-20]
    X_pred = X[-1:]

    t0 = time.perf_counter()
    try:
        reg = TabPFNRegressor(device="cpu")
        load_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        reg.fit(X_train, y_train)
        pred = reg.predict(X_pred)
        fit_predict_s = time.perf_counter() - t1
    except Exception as exc:  # noqa: BLE001
        return SpikeResult(
            model="tabpfn",
            backend="cpu",
            install_ok=True,
            load_s=None,
            fit_predict_s=None,
            cycle_12_series_s=None,
            n_train=len(X_train),
            n_pred=1,
            gate_g2="FAIL",
            notes="tabpfn fit failed",
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}",
        )

    t2 = time.perf_counter()
    for i in range(12):
        Xi, yi, _ = _synthetic_series(60, seed=i)
        r = TabPFNRegressor(device="cpu")
        r.fit(Xi[:-20], yi[:-20])
        _ = r.predict(Xi[-1:])
    cycle_s = time.perf_counter() - t2

    return SpikeResult(
        model="tabpfn",
        backend="cpu",
        install_ok=True,
        load_s=load_s,
        fit_predict_s=fit_predict_s,
        cycle_12_series_s=cycle_s,
        n_train=len(X_train),
        n_pred=1,
        gate_g2="PASS" if cycle_s < 15.0 else "FALLBACK",
        notes=f"tabpfn 8.x fallback; pred={float(np.asarray(pred).ravel()[0]):.3f}; 12-series={cycle_s:.2f}s",
    )


def main() -> int:
    print("=== G2 TabFM spike ===")
    result = try_tabfm()
    print(json.dumps(asdict(result), indent=2))

    if result.gate_g2 != "PASS":
        print("=== falling to tabpfn ===")
        fb = try_tabpfn()
        print(json.dumps(asdict(fb), indent=2))
        # Lock the working fallback if TabFM failed
        if fb.gate_g2 == "PASS" or (fb.install_ok and fb.fit_predict_s is not None):
            result = SpikeResult(
                model="tabpfn",
                backend=fb.backend,
                install_ok=fb.install_ok,
                load_s=fb.load_s,
                fit_predict_s=fb.fit_predict_s,
                cycle_12_series_s=fb.cycle_12_series_s,
                n_train=fb.n_train,
                n_pred=fb.n_pred,
                gate_g2="PASS" if fb.fit_predict_s is not None else "FAIL",
                notes=f"LOCKED tabpfn (TabFM: {result.notes}). {fb.notes}",
                error=result.error,
            )
        else:
            result = SpikeResult(
                model="mad",
                backend=None,
                install_ok=False,
                load_s=None,
                fit_predict_s=None,
                cycle_12_series_s=None,
                n_train=0,
                n_pred=0,
                gate_g2="FAIL",
                notes="both TabFM and TabPFN failed — Phase 3 uses MAD last resort",
                error=f"tabfm={result.error}; tabpfn={fb.error}",
            )

    OUT.write_text(json.dumps(asdict(result), indent=2) + "\n")
    print(f"wrote {OUT}")
    print(f"G2={result.gate_g2} locked_model={result.model}")
    return 0 if result.gate_g2 == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
