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


def cache_snapshot() -> dict[str, Any]:
    """Enriched Griffin status for HQ MAD strip (Wave B)."""
    snap = dict(_CACHE)
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
    snap["honesty"] = (
        "Griffin estimator = MAD (median/MAD robust z-score). "
        "TabFM not live; TabPFN optional behind TABPFN_TOKEN."
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
    result = mad_judge(values, observed=observed, noise_floor=floor)

    now_ms = int(time.time() * 1000)
    _CACHE["series"][series_id] = {
        **result,
        "sparkline": values[-60:],
        "updated_ms": now_ms,
    }
    _CACHE["last_cycle_ms"] = now_ms
    _CACHE["last_evaluate_ms"] = now_ms
    _CACHE["status"] = result["status"]
    _CACHE["estimator"] = "mad"
    _CACHE["model"] = "mad"
    if not _CACHE.get("series_source"):
        _CACHE["series_source"] = source if source != "none" else None

    if not result.get("outlier"):
        return {
            "series_id": series_id,
            **result,
            "fired": False,
            "estimator": "mad",
            "series_source": _CACHE.get("series_source"),
        }

    now = now_ms
    if now - _last_fire.get(series_id, 0) < COOLDOWN_MS:
        return {
            "series_id": series_id,
            **result,
            "fired": False,
            "cooldown": True,
            "estimator": "mad",
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
            f"griffin MAD outlier on {series_id} z={result.get('z')}",
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
        "estimator": "mad",
        "series_source": _CACHE.get("series_source"),
    }


async def griffin_loop(get_conn: Callable, *, cadence_s: float = 60.0) -> None:
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
            _CACHE["model"] = "mad"
            _CACHE["estimator"] = "mad"
        except Exception:  # noqa: BLE001
            logger.exception("griffin cycle failed")
        await asyncio.sleep(cadence_s)
