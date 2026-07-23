"""Griffin — MAD anomaly worker (G2 locked; docs/07).

Primary TabFM too slow; TabPFN needs TABPFN_TOKEN. Phase 3 ships robust
z-score on rolling median/MAD. Narration = statistical baseline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("arcnet.griffin")

# In-memory forecast cache for UI sparkline (docs/12: not a table)
_CACHE: dict[str, Any] = {
    "model": "mad",
    "estimator": "mad",
    "status": "cold",
    "series": {},
    "proxy_series": {},  # sqlite_proxy only — never written to seed path
    "series_source": None,  # seed | sqlite_proxy | signoz | None
    "last_cycle_ms": None,
    "last_evaluate_ms": None,
    "last_anomaly": None,
    "anomalies": [],
}

ALLOWLIST = [
    "arcnet.tokens.total|agent_j",
    "arcnet.cost.usd|agent_j",
    "arcnet.tool.calls|agent_j",
]

NOISE_FLOOR = {
    "arcnet.tokens.total": 50.0,
    "arcnet.cost.usd": 0.001,
    "arcnet.tool.calls": 2.0,
}

COOLDOWN_MS = 5 * 60 * 1000
_last_fire: dict[str, int] = {}

# TabFM async worker state (P7-B) — opt-in via ARCNET_TABFM=1
_TABFM_STATE: dict[str, Any] = {
    "enabled": False,
    "loaded": False,
    "last_forecast_ms": None,
    "degrade_reason": None,
    "degraded": False,
    "forecast_succeeded": False,
}
_TABFM_THREAD: threading.Thread | None = None
_TABFM_START_LOCK = threading.Lock()


def _series_path() -> Path:
    env = os.getenv("ARCNET_GRIFFIN_SERIES")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data" / "griffin_series.json"


def load_series() -> dict[str, list[dict[str, float]]]:
    path = _series_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_series(data: dict[str, list[dict[str, float]]]) -> None:
    path = _series_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def mad_judge(
    values: list[float],
    *,
    observed: float | None = None,
    z_thresh: float = 3.5,
    noise_floor: float = 1.0,
    min_points: int = 30,
) -> dict[str, Any]:
    """Robust z-score on rolling median/MAD. Returns forecast band + outlier flag."""
    if len(values) < min_points:
        return {
            "status": "warming",
            "n": len(values),
            "outlier": False,
            "forecast": None,
            "band_lo": None,
            "band_hi": None,
            "observed": observed,
        }
    hist = values[:-1] if observed is None and len(values) > min_points else values
    obs = float(observed if observed is not None else values[-1])
    med = _median(hist)
    abs_dev = [abs(v - med) for v in hist]
    mad = _median(abs_dev) or 1e-9
    # Consistent estimator of σ
    sigma = 1.4826 * mad
    z = abs(obs - med) / sigma if sigma > 0 else 0.0
    band = 3.0 * sigma
    outlier = z >= z_thresh and abs(obs - med) > noise_floor
    return {
        "status": "ready",
        "n": len(hist),
        "outlier": outlier,
        "forecast": med,
        "band_lo": med - band,
        "band_hi": med + band,
        "observed": obs,
        "z": round(z, 3),
        "mad": mad,
        "sigma": sigma,
    }


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def tabfm_enabled() -> bool:
    return os.getenv("ARCNET_TABFM", "").strip().lower() in ("1", "true", "yes")


def tabfm_cadence_s() -> float:
    return float(os.getenv("ARCNET_TABFM_CADENCE_S", "360"))


def tabfm_status_snapshot() -> dict[str, Any]:
    return {
        "enabled": tabfm_enabled(),
        "loaded": bool(_TABFM_STATE["loaded"]),
        "last_forecast_ms": _TABFM_STATE["last_forecast_ms"],
        "degrade_reason": _TABFM_STATE["degrade_reason"],
    }


def tabfm_forecast_live() -> bool:
    return bool(_TABFM_STATE["forecast_succeeded"]) and not bool(_TABFM_STATE["degraded"])


def _degrade_tabfm(reason: str) -> None:
    if _TABFM_STATE["degraded"]:
        return
    _TABFM_STATE["degraded"] = True
    _TABFM_STATE["degrade_reason"] = reason
    logger.warning("TabFM worker degrading to MAD permanently: %s", reason)


def judge_with_point_forecast(
    values: list[float],
    *,
    point_forecast: float,
    observed: float | None = None,
    noise_floor: float = 1.0,
    z_thresh: float = 3.5,
    min_points: int = 30,
) -> dict[str, Any]:
    """MAD sigma/bands with an external point forecast (TabFM path)."""
    result = mad_judge(
        values,
        observed=observed,
        noise_floor=noise_floor,
        z_thresh=z_thresh,
        min_points=min_points,
    )
    if result["status"] != "ready":
        return result
    obs = float(result["observed"])
    sigma = float(result.get("sigma") or 1e-9)
    fc = float(point_forecast)
    z = abs(obs - fc) / sigma if sigma > 0 else 0.0
    band = 3.0 * sigma
    outlier = z >= z_thresh and abs(obs - fc) > noise_floor
    return {
        **result,
        "forecast": fc,
        "band_lo": fc - band,
        "band_hi": fc + band,
        "z": round(z, 3),
        "outlier": outlier,
    }


def _pick_highest_priority_series(series: dict[str, list[dict[str, float]]]) -> str | None:
    """ALLOWLIST order — N=1 series per TabFM cycle (docs/_phase7_g7.json)."""
    for sid in ALLOWLIST:
        pts = series.get(sid) or []
        if len(pts) >= 30:
            return sid
    return None


def run_tabfm_cycle_once(get_conn: Callable) -> None:
    """Single TabFM forecast cycle (tests + worker thread)."""
    if not tabfm_enabled() or _TABFM_STATE["degraded"]:
        return

    from arcnet_server.tabfm_worker import forecast as tabfm_forecast

    try:
        ensure_series_warm(get_conn)
        series = active_series()
        series_id = _pick_highest_priority_series(series)
        if not series_id:
            return

        points = series.get(series_id) or []
        values = [float(p["v"]) for p in points]
        out = tabfm_forecast(values, features=None, backend="tabfm")

        if out.get("status") == "error" or not out.get("predictions"):
            detail = out.get("detail") if isinstance(out.get("detail"), dict) else {}
            reason = (
                detail.get("error")
                or detail.get("message")
                or out.get("status")
                or "tabfm_forecast_failed"
            )
            _degrade_tabfm(str(reason))
            return

        pred = float(out["predictions"][0])
        _TABFM_STATE["loaded"] = True
        _TABFM_STATE["last_forecast_ms"] = int(time.time() * 1000)
        _TABFM_STATE["forecast_succeeded"] = True

        evaluate_series(
            get_conn,
            series_id=series_id,
            observed=None,
            point_forecast=pred,
            estimator_label="tabfm",
        )
    except Exception as exc:  # noqa: BLE001
        _degrade_tabfm(f"{type(exc).__name__}: {exc}")


def _tabfm_worker_loop(get_conn: Callable) -> None:
    cadence = tabfm_cadence_s()
    logger.info("tabfm worker start cadence=%.1fs N=1", cadence)
    while not _TABFM_STATE["degraded"]:
        run_tabfm_cycle_once(get_conn)
        time.sleep(cadence)


def start_tabfm_worker(get_conn: Callable) -> None:
    """Daemon thread — never blocks request handlers."""
    global _TABFM_THREAD
    if not tabfm_enabled():
        return
    with _TABFM_START_LOCK:
        if _TABFM_THREAD is not None and _TABFM_THREAD.is_alive():
            return
        _TABFM_STATE["enabled"] = True
        _TABFM_THREAD = threading.Thread(
            target=_tabfm_worker_loop,
            args=(get_conn,),
            name="arcnet-tabfm",
            daemon=True,
        )
        _TABFM_THREAD.start()


def reset_tabfm_state_for_tests() -> None:
    """Isolate TabFM worker globals between tests."""
    global _TABFM_THREAD
    _TABFM_STATE.update(
        {
            "enabled": False,
            "loaded": False,
            "last_forecast_ms": None,
            "degrade_reason": None,
            "degraded": False,
            "forecast_succeeded": False,
        }
    )
    _TABFM_THREAD = None


def cache_snapshot() -> dict[str, Any]:
    """Enriched Griffin status for HQ MAD strip (Wave B)."""
    snap = dict(_CACHE)
    snap["tabfm"] = tabfm_status_snapshot()
    if tabfm_forecast_live():
        snap["estimator"] = "tabfm"
        snap["model"] = "tabfm"
    else:
        snap["estimator"] = "mad"
        snap["model"] = "mad"
    series = snap.get("series") if isinstance(snap.get("series"), dict) else {}
    warmth: dict[str, Any] = {}
    ready_n = 0
    warming_n = 0
    for sid, meta in series.items():
        if not isinstance(meta, dict):
            continue
        st = meta.get("status") or "cold"
        warmth[sid] = {
            "status": st,
            "n": meta.get("n"),
            "outlier": bool(meta.get("outlier")),
            "updated_ms": meta.get("updated_ms"),
            "z": meta.get("z"),
        }
        if st == "ready":
            ready_n += 1
        elif st == "warming":
            warming_n += 1
    anomalies = list(snap.get("anomalies") or [])
    last = snap.get("last_anomaly")
    if last is None and anomalies:
        last = anomalies[0]
    overall = snap.get("status") or "cold"
    if ready_n > 0:
        overall = "ready"
    elif warming_n > 0:
        overall = "warming"
    elif series:
        overall = snap.get("status") or "warming"
    else:
        overall = "cold" if not snap.get("series_source") else "warming"
    snap["status"] = overall
    snap["warmth"] = warmth
    snap["series_count"] = len(series)
    snap["ready_count"] = ready_n
    snap["warming_count"] = warming_n
    snap["last_anomaly"] = last
    if tabfm_forecast_live():
        snap["honesty"] = (
            "Griffin estimator = TabFM (google/tabfm-1.0.0-pytorch regression) "
            "with MAD z-score bands; N=1 series per 360s async cycle."
        )
    elif tabfm_enabled() and _TABFM_STATE["degraded"]:
        snap["honesty"] = (
            f"Griffin estimator = MAD (TabFM enabled but degraded: "
            f"{_TABFM_STATE['degrade_reason']}). TabPFN optional behind TABPFN_TOKEN."
        )
    else:
        snap["honesty"] = (
            "Griffin estimator = MAD (median/MAD robust z-score). "
            "TabFM = Phase 7, live only when worker active (ARCNET_TABFM=1)."
        )
    return snap


def derive_sqlite_proxy_series(get_conn: Callable) -> dict[str, list[dict[str, float]]]:
    """Crude per-session usage series from SQLite — honest ``sqlite_proxy`` source.

    Not a substitute for OTLP metrics; high noise floor + warming gates apply.
    """
    conn = get_conn()
    rows = conn.execute(
        """SELECT agent_id, started_at, usage FROM sessions
           WHERE usage IS NOT NULL AND started_at IS NOT NULL
           ORDER BY started_at DESC LIMIT 200"""
    ).fetchall()
    buckets: dict[str, list[dict[str, float]]] = {}
    for row in rows:
        agent_id = row[0] or "unknown"
        t = float(row[1] or 0) / 1000.0  # ms → s for seed-compatible shape
        usage_raw = row[2]
        try:
            usage = json.loads(usage_raw) if isinstance(usage_raw, str) else (usage_raw or {})
        except json.JSONDecodeError:
            usage = {}
        if not isinstance(usage, dict):
            usage = {}
        tokens = usage.get("total_tokens") or usage.get("tokens") or usage.get("prompt_tokens")
        cost = usage.get("cost_usd") or usage.get("cost")
        tools = usage.get("tool_calls") or usage.get("tools")
        mapping = [
            ("arcnet.tokens.total", tokens),
            ("arcnet.cost.usd", cost),
            ("arcnet.tool.calls", tools),
        ]
        for metric, val in mapping:
            if val is None:
                continue
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            sid = f"{metric}|{agent_id}"
            buckets.setdefault(sid, []).append({"t": t, "v": v})
    # Chronological + cap
    for sid, pts in list(buckets.items()):
        pts.sort(key=lambda p: p["t"])
        buckets[sid] = pts[-120:]
    return buckets


def active_series() -> dict[str, list[dict[str, float]]]:
    """Series used for evaluate: seed file wins; else in-memory sqlite proxy."""
    seeded = load_series()
    if seeded:
        return seeded
    proxy = _CACHE.get("proxy_series")
    return proxy if isinstance(proxy, dict) else {}


def ensure_series_warm(get_conn: Callable) -> str:
    """Load series preferring seed file, else SQLite proxy. Returns source label.

    Proxy snapshots stay in-memory only so warm-up never freezes into a seed file
    that would skip later SQLite refreshes and mislabel Fleet Health as seed.
    """
    seeded = load_series()
    if seeded:
        _CACHE["series_source"] = "seed"
        return "seed"
    proxy = derive_sqlite_proxy_series(get_conn)
    if proxy:
        _CACHE["proxy_series"] = proxy
        _CACHE["series_source"] = "sqlite_proxy"
        return "sqlite_proxy"
    _CACHE["proxy_series"] = {}
    _CACHE["series_source"] = None
    return "none"


def evaluate_series(
    get_conn: Callable,
    *,
    series_id: str,
    observed: float | None = None,
    point_forecast: float | None = None,
    estimator_label: str = "mad",
) -> dict[str, Any]:
    """Judge one series; on outlier emit signal source=griffin + update cache."""
    if not active_series().get(series_id):
        ensure_series_warm(get_conn)
    source = _CACHE.get("series_source") or ensure_series_warm(get_conn)
    series = active_series()
    points = series.get(series_id) or []
    values = [float(p["v"]) for p in points]
    if observed is not None:
        values = values + [float(observed)]
        # Persist spike only for intentional seed files — never promote proxy→seed
        points = list(points) + [{"t": time.time(), "v": float(observed)}]
        if source == "seed":
            seeded = load_series()
            seeded[series_id] = points[-500:]
            save_series(seeded)
        else:
            proxy = dict(_CACHE.get("proxy_series") or {})
            proxy[series_id] = points[-500:]
            _CACHE["proxy_series"] = proxy

    metric = series_id.split("|", 1)[0]
    agent_id = series_id.split("|", 1)[1] if "|" in series_id else "agent_j"
    floor = NOISE_FLOOR.get(metric, 1.0)
    if point_forecast is not None:
        result = judge_with_point_forecast(
            values,
            point_forecast=point_forecast,
            observed=observed,
            noise_floor=floor,
        )
    else:
        result = mad_judge(values, observed=observed, noise_floor=floor)

    now_ms = int(time.time() * 1000)
    _CACHE["series"][series_id] = {
        **result,
        "sparkline": values[-60:],
        "updated_ms": now_ms,
        "estimator": estimator_label,
    }
    _CACHE["last_cycle_ms"] = now_ms
    _CACHE["last_evaluate_ms"] = now_ms
    _CACHE["status"] = result["status"]
    if not _CACHE.get("series_source"):
        _CACHE["series_source"] = source if source != "none" else None

    est = estimator_label
    if not result.get("outlier"):
        return {
            "series_id": series_id,
            **result,
            "fired": False,
            "estimator": est,
            "series_source": _CACHE.get("series_source"),
        }

    now = now_ms
    if now - _last_fire.get(series_id, 0) < COOLDOWN_MS:
        return {
            "series_id": series_id,
            **result,
            "fired": False,
            "cooldown": True,
            "estimator": est,
            "series_source": _CACHE.get("series_source"),
        }

    _last_fire[series_id] = now
    anomaly = {
        "series_id": series_id,
        "agent_id": agent_id,
        "metric": metric,
        "observed": result["observed"],
        "forecast": result["forecast"],
        "z": result.get("z"),
        "ts_ms": now,
        "fingerprint": f"{series_id}:{result.get('z')}:{now}",
    }
    _CACHE["anomalies"] = ([anomaly] + list(_CACHE.get("anomalies") or []))[:20]
    _CACHE["last_anomaly"] = anomaly

    # Signal bus (source=griffin) — agent-scoped note (docs/07). Griffin series
    # carry no session attribution; a null-session kill would broadcast to every
    # live session of the agent. Kills stay session-scoped (runner/HQ posts them).
    kind = "note"
    severity = "critical" if metric in ("arcnet.tokens.total", "arcnet.cost.usd", "arcnet.tool.calls") else "warn"
    signal_id = f"sig_{secrets.token_hex(4)}"
    judge_tag = "TabFM" if estimator_label == "tabfm" else "MAD"
    conn = get_conn()
    conn.execute(
        """INSERT INTO signals
           (signal_id, session_id, agent_id, kind, severity, reason, evidence_link, guidance, source, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            signal_id,
            None,
            agent_id,
            kind,
            severity,
            f"griffin {judge_tag} outlier on {series_id} z={result.get('z')}",
            None,
            f"observed={result['observed']} forecast={result['forecast']} band=[{result['band_lo']},{result['band_hi']}]",
            "griffin",
            "pending",
            now,
        ),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM signals WHERE signal_id=?", (signal_id,)).fetchone())
    try:
        from arcnet_server.bus import BUS

        BUS.publish("signal", row)
    except Exception as exc:  # noqa: BLE001
        logger.warning("griffin signal bus publish failed: %s", exc)

    # Best-effort OTel metric if SDK runtime is live in-process (usually not on server)
    try:
        from opentelemetry import metrics

        meter = metrics.get_meter("arcnet.griffin")
        counter = meter.create_counter("arcnet.anomaly")
        counter.add(
            1,
            {
                "metric": metric,
                "agent_id": agent_id,
                "direction": "high" if (result["observed"] or 0) > (result["forecast"] or 0) else "low",
                "severity": str(result.get("z") or 0),
            },
        )
    except Exception:  # noqa: BLE001
        logger.debug("otel anomaly emit skipped", exc_info=True)

    return {
        "series_id": series_id,
        **result,
        "fired": True,
        "signal_id": signal_id,
        "signal": row,
        "estimator": est,
        "series_source": _CACHE.get("series_source"),
    }


async def griffin_loop(get_conn: Callable, *, cadence_s: float = 60.0) -> None:
    start_tabfm_worker(get_conn)
    logger.info("griffin loop start cadence=%.1fs model=mad", cadence_s)
    while True:
        try:
            ensure_series_warm(get_conn)
            series = active_series()
            if not series:
                _CACHE["status"] = "cold"
            for sid in ALLOWLIST:
                if sid in series:
                    evaluate_series(get_conn, series_id=sid, observed=None)
        except Exception:  # noqa: BLE001
            logger.exception("griffin cycle failed")
        await asyncio.sleep(cadence_s)
