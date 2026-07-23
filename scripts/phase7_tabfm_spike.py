#!/usr/bin/env python3
"""Phase 7 gate G7 — TabFM CPU re-measure (P7-A; docs/07, docs/22).

Re-measures google/tabfm-1.0.0-pytorch subfolder=regression on this machine.
Does NOT lock runtime to TabFM. Writes docs/_phase7_g7.json with measurements
+ decision (series_count, cadence_s, hardware, verdict).

Uses HF cache when present (~/.cache/huggingface). No TabPFN path.
"""

from __future__ import annotations

import json
import os
import platform
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "_phase7_g7.json"
CHECKPOINT = "google/tabfm-1.0.0-pytorch"
SUBFOLDER = "regression"
CYCLE_BUDGET_S = 15.0
N_TRAIN_TAIL_HOLD = 20
SERIES_LEN = 60


@dataclass
class SpikeResult:
    status: str  # OK | BLOCKED | FAIL
    model: str
    checkpoint: str
    subfolder: str
    backend: str | None
    install_ok: bool
    weights_cached: bool | None
    hardware: dict[str, Any]
    load_s: float | None
    fit_predict_s: float | None
    fit_predict_per_series_s: list[float] = field(default_factory=list)
    projected_cycle_s: dict[str, float | None] = field(default_factory=dict)
    n_train: int = 0
    n_pred: int = 0
    decision: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    error: str | None = None
    prior_g2: dict[str, Any] | None = None


def _hf_cache_has_tabfm() -> bool:
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    marker = hub / "models--google--tabfm-1.0.0-pytorch"
    if not marker.exists():
        return False
    # Prefer regression snapshot presence
    snaps = list(marker.glob("snapshots/*/regression/*"))
    return bool(snaps) or any(marker.rglob("pytorch_model.bin"))


def _hardware() -> dict[str, Any]:
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "device": "cpu",
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["device"] = "cuda"
            info["cuda_name"] = torch.cuda.get_device_name(0)
    except Exception:  # noqa: BLE001
        info["torch"] = None
        info["cuda_available"] = False
    return info


def _synthetic_series(n: int = SERIES_LEN, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float64)
    y = 10.0 + 0.05 * t + 2.0 * np.sin(t / 7.0) + rng.normal(0, 0.4, size=n)
    roll5_mean = np.convolve(y, np.ones(5) / 5, mode="same")
    roll5_std = np.array(
        [y[max(0, i - 4) : i + 1].std() if i > 0 else 0.0 for i in range(n)],
        dtype=np.float64,
    )
    lag1 = np.concatenate([[y[0]], y[:-1]])
    X = np.column_stack([t, t % 60, roll5_mean, roll5_std, lag1])
    return X, y


def _load_prior_g2() -> dict[str, Any] | None:
    path = ROOT / "docs" / "_phase2_g2.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _decide(
    *,
    load_s: float | None,
    per_series: list[float],
    hardware: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    """Lock series count + cadence for P7-B given measured CPU latency."""
    med = float(np.median(per_series)) if per_series else None
    device = hardware.get("device") or "cpu"

    if status != "OK" or med is None:
        return {
            "series_count": 0,
            "cadence_s": None,
            "hardware": device,
            "verdict": "BLOCKED_NO_MEASUREMENT",
            "rationale": "No live TabFM timings; keep MAD runtime until spike OK.",
            "cycle_budget_s": CYCLE_BUDGET_S,
        }

    # Prefer largest N that fits budget with headroom; else lengthen cadence.
    candidates = [1, 2, 3, 12]
    fits = [n for n in candidates if med * n <= CYCLE_BUDGET_S * 0.9]
    if fits:
        series_count = max(fits)
        cadence_s = 60
        verdict = "SUBSET_ASYNC_OK" if series_count < 12 else "FULL_12_IN_BUDGET"
    else:
        series_count = 1
        # Cadence must cover fit+predict + small overhead; min 60s product loop.
        cadence_s = max(60, int(np.ceil(med * 1.25 / 15.0) * 15))
        if med > CYCLE_BUDGET_S:
            cadence_s = max(cadence_s, int(np.ceil(med / 15.0) * 60))
        verdict = "SINGLE_SERIES_LONG_CADENCE"

    if device == "cpu" and med > 5.0:
        # CPU path is the measured default; GPU optional later, not required for P7-A.
        hardware_choice = "cpu"
    else:
        hardware_choice = device

    return {
        "series_count": series_count,
        "cadence_s": cadence_s,
        "hardware": hardware_choice,
        "verdict": verdict,
        "median_fit_predict_s": round(med, 3),
        "load_s": round(load_s, 3) if load_s is not None else None,
        "cycle_budget_s": CYCLE_BUDGET_S,
        "rationale": (
            f"median fit+predict {med:.2f}s/series on {hardware_choice}; "
            f"choose N={series_count} @ {cadence_s}s cadence; "
            "async worker + MAD degrade required; not wired to runtime in P7-A."
        ),
    }


def try_tabfm() -> SpikeResult:
    notes: list[str] = []
    hardware = _hardware()
    cached = _hf_cache_has_tabfm()
    prior = _load_prior_g2()
    base = dict(
        model="tabfm",
        checkpoint=CHECKPOINT,
        subfolder=SUBFOLDER,
        backend="pytorch",
        weights_cached=cached,
        hardware=hardware,
        prior_g2=(prior.get("tabfm") if isinstance(prior, dict) else None),
    )

    try:
        import safetensors  # noqa: F401 — required by huggingface_hub safetensor path
        from tabfm import TabFMRegressor, tabfm_v1_0_0_pytorch as tabfm_v1_0_0
    except Exception as exc:  # noqa: BLE001
        notes.append("tabfm import failed (need tabfm[pytorch] + safetensors)")
        if not cached:
            notes.append("HF cache empty/missing regression weights")
        res = SpikeResult(
            status="BLOCKED",
            install_ok=False,
            load_s=None,
            fit_predict_s=None,
            notes="; ".join(notes),
            error=f"{type(exc).__name__}: {exc}",
            **base,
        )
        res.decision = _decide(load_s=None, per_series=[], hardware=hardware, status="BLOCKED")
        res.projected_cycle_s = {str(n): None for n in (1, 2, 3, 12)}
        return res

    notes.append("import tabfm pytorch backend ok")
    notes.append(f"weights_cached={cached}")

    X, y = _synthetic_series(SERIES_LEN, seed=0)
    X_train, y_train = X[:-N_TRAIN_TAIL_HOLD], y[:-N_TRAIN_TAIL_HOLD]
    X_pred = X[-1:]

    # Cap wall time: full 12-series can be ~15+ min on CPU; measure up to max_series.
    max_series = int(os.getenv("ARCNET_TABFM_SPIKE_SERIES", "7"))
    max_series = max(1, min(12, max_series))

    t0 = time.perf_counter()
    try:
        try:
            model = tabfm_v1_0_0.load(model_type="regression")
        except TypeError:
            model = tabfm_v1_0_0.load()
        load_s = time.perf_counter() - t0
        notes.append(f"weights load {load_s:.2f}s")
        print(f"load_s={load_s:.3f}", flush=True)
    except Exception as exc:  # noqa: BLE001
        status = "BLOCKED" if "token" in str(exc).lower() or "401" in str(exc) else "FAIL"
        if not cached:
            status = "BLOCKED"
            notes.append("load failed and cache incomplete — need HF download")
        res = SpikeResult(
            status=status,
            install_ok=True,
            load_s=None,
            fit_predict_s=None,
            n_train=len(X_train),
            n_pred=1,
            notes="; ".join(notes),
            error=f"load failed: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}",
            **base,
        )
        res.decision = _decide(load_s=None, per_series=[], hardware=hardware, status=status)
        res.projected_cycle_s = {str(n): None for n in (1, 2, 3, 12)}
        return res

    t1 = time.perf_counter()
    try:
        reg = TabFMRegressor(model=model)
        reg.fit(X_train, y_train)
        pred = reg.predict(X_pred)
        fit_predict_s = time.perf_counter() - t1
        notes.append(
            f"single fit+predict {fit_predict_s:.3f}s "
            f"pred={float(np.asarray(pred).ravel()[0]):.3f}"
        )
        print(f"fit_predict_s={fit_predict_s:.3f}", flush=True)
    except Exception as exc:  # noqa: BLE001
        res = SpikeResult(
            status="FAIL",
            install_ok=True,
            load_s=load_s,
            fit_predict_s=None,
            n_train=len(X_train),
            n_pred=1,
            notes="; ".join(notes),
            error=f"fit/predict failed: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-800:]}",
            **base,
        )
        res.decision = _decide(load_s=load_s, per_series=[], hardware=hardware, status="FAIL")
        res.projected_cycle_s = {str(n): None for n in (1, 2, 3, 12)}
        return res

    # Per-series timings (reuse loaded weights; re-fit each — Griffin pattern)
    per_series: list[float] = []
    for i in range(max_series):
        Xi, yi = _synthetic_series(SERIES_LEN, seed=i)
        Xi_train, yi_train = Xi[:-N_TRAIN_TAIL_HOLD], yi[:-N_TRAIN_TAIL_HOLD]
        t_i = time.perf_counter()
        reg_i = TabFMRegressor(model=model)
        reg_i.fit(Xi_train, yi_train)
        _ = reg_i.predict(Xi[-1:])
        dt = time.perf_counter() - t_i
        per_series.append(dt)
        print(f"series[{i}]={dt:.3f}s", flush=True)

    median_s = float(np.median(per_series))
    projected = {str(n): round(median_s * n, 3) for n in (1, 2, 3, 12)}
    notes.append(
        f"{len(per_series)}-series measured sum={sum(per_series):.2f}s "
        f"median={median_s:.2f}s/series projected={projected}"
    )

    decision = _decide(
        load_s=load_s,
        per_series=per_series,
        hardware=hardware,
        status="OK",
    )
    decision["measured_series_count"] = len(per_series)
    notes.append(f"decision={decision.get('verdict')} N={decision.get('series_count')}")

    return SpikeResult(
        status="OK",
        install_ok=True,
        load_s=round(load_s, 3),
        fit_predict_s=round(fit_predict_s, 3),
        fit_predict_per_series_s=[round(x, 3) for x in per_series],
        projected_cycle_s=projected,
        n_train=len(X_train),
        n_pred=1,
        decision=decision,
        notes="; ".join(notes),
        **base,
    )


def main() -> int:
    print("=== P7-A / G7 TabFM spike re-measure ===")
    result = try_tabfm()
    payload = asdict(result)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    print(f"wrote {OUT}")
    print(f"status={result.status} decision={result.decision.get('verdict')}")
    # Measurement packet always exits 0 when JSON written (BLOCKED is honest).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
