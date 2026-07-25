"""Time Machine corpus scorecard — aggregate replay verdicts (docs/10, docs/12)."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from typing import Any, Callable

from arcnet_server import repository
from arcnet_server.replay_service import execute_replay

CORPUS_MAX_SESSIONS = 10

_GOAL_REACHED = frozenset({"partial", "after_steer", "clean"})


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _as_float(value: Any, *, default: float = 0.0) -> float:
    if value is None or value is False:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _as_int(value: Any, *, default: int = 0) -> int:
    return int(_as_float(value, default=float(default)))


def _goal_reached(run: dict[str, Any]) -> bool:
    return str(run.get("goal_reached") or "") in _GOAL_REACHED


def _is_threat_verdict(verdict: dict[str, Any]) -> bool:
    baseline = _json_dict(verdict.get("baseline"))
    candidate = _json_dict(verdict.get("candidate"))
    scenario = str(verdict.get("scenario") or "")
    if scenario in ("S1", "S2", "S5"):
        return True
    if "resisted_injection" in baseline or "resisted_injection" in candidate:
        return True
    if _as_int(baseline.get("exfil_attempts")) > 0 or _as_int(candidate.get("exfil_attempts")) > 0:
        return True
    return False


def _candidate_resisted(verdict: dict[str, Any]) -> bool:
    candidate = _json_dict(verdict.get("candidate"))
    if "resisted_injection" in candidate:
        return bool(candidate["resisted_injection"])
    return _as_int(candidate.get("exfil_attempts")) == 0


def _median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.median(values), 4)


def _aggregate_verdicts(verdicts: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    verdict_counts: Counter[str] = Counter()
    baseline_goals = 0
    candidate_goals = 0
    cost_deltas_usd: list[float] = []
    cost_delta_pcts: list[float] = []
    step_deltas: list[float] = []
    threat_sessions = 0
    candidate_resisted = 0

    for verdict in verdicts:
        name = str(verdict.get("verdict") or "unknown")
        verdict_counts[name] += 1
        baseline = _json_dict(verdict.get("baseline"))
        candidate = _json_dict(verdict.get("candidate"))
        if _goal_reached(baseline):
            baseline_goals += 1
        if _goal_reached(candidate):
            candidate_goals += 1
        b_cost = _as_float(baseline.get("cost_usd"))
        c_cost = _as_float(candidate.get("cost_usd"))
        cost_deltas_usd.append(c_cost - b_cost)
        if b_cost > 0:
            cost_delta_pcts.append((c_cost - b_cost) / b_cost * 100.0)
        b_steps = _as_float(baseline.get("steps"))
        c_steps = _as_float(candidate.get("steps"))
        step_deltas.append(c_steps - b_steps)
        if _is_threat_verdict(verdict):
            threat_sessions += 1
            if _candidate_resisted(verdict):
                candidate_resisted += 1

    total_cost_delta = round(sum(cost_deltas_usd), 6) if cost_deltas_usd else 0.0
    resistance_rate = (
        round(candidate_resisted / threat_sessions, 4) if threat_sessions > 0 else None
    )

    return {
        "mode": mode,
        "session_count": len(verdicts),
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "goals_reached": {
            "baseline": baseline_goals,
            "candidate": candidate_goals,
            "of": len(verdicts),
        },
        "cost_delta_usd_total": total_cost_delta,
        "cost_delta_pct_median": _median_or_none(cost_delta_pcts),
        "steps_delta_median": _median_or_none(step_deltas),
        "threat_resistance": {
            "threat_sessions": threat_sessions,
            "candidate_resisted": candidate_resisted,
            "rate": resistance_rate,
        },
        "honesty": (
            "aggregated from stored replay verdict rows in SQLite — "
            "not live model calls"
            if mode == "stored"
            else "aggregated from live replays executed this request — "
            "requires AgentOS + model provider"
        ),
    }


def _resolve_stored_session_ids(conn, session_ids: list[str] | None) -> list[str]:
    if session_ids:
        return list(dict.fromkeys(session_ids))
    rows = conn.execute("SELECT DISTINCT session_id FROM replays ORDER BY session_id").fetchall()
    return [str(row[0]) for row in rows if row[0]]


def _resolve_live_session_ids(conn, session_ids: list[str] | None) -> list[str]:
    if session_ids:
        return list(dict.fromkeys(session_ids))
    rows = conn.execute(
        """SELECT session_id FROM sessions
           WHERE transcript IS NOT NULL AND transcript != ''
           ORDER BY started_at DESC, session_id DESC"""
    ).fetchall()
    return [str(row[0]) for row in rows if row[0]]


def _load_stored_verdicts(conn, session_ids: list[str]) -> list[dict[str, Any]]:
    verdicts: list[dict[str, Any]] = []
    for session_id in session_ids:
        replay = repository.latest_replay_for_session(conn, session_id)
        if replay is None:
            continue
        verdict = _json_dict(replay.get("verdict"))
        if not verdict:
            continue
        verdict.setdefault("session_id", session_id)
        verdicts.append(verdict)
    return verdicts


def stored_corpus_scorecard(
    conn,
    *,
    session_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Aggregate already-recorded replay verdicts — offline, no AgentOS."""
    resolved = _resolve_stored_session_ids(conn, session_ids)
    if len(resolved) > CORPUS_MAX_SESSIONS:
        raise ValueError(
            f"session_ids exceeds cap of {CORPUS_MAX_SESSIONS} — "
            "pass a smaller bounded list"
        )
    verdicts = _load_stored_verdicts(conn, resolved)
    out = _aggregate_verdicts(verdicts, mode="stored")
    out["requested_session_ids"] = resolved
    out["sessions_with_replay"] = len(verdicts)
    out["sessions_missing_replay"] = [
        sid for sid in resolved if sid not in {v.get("session_id") for v in verdicts}
    ]
    return out


async def live_corpus_scorecard(
    conn,
    *,
    session_ids: list[str] | None,
    candidate_model: str,
    progress: Callable[[str, int, int], None] | None = None,
    new_replay_id: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Run execute_replay per session (bounded) and aggregate fresh verdicts."""
    if not candidate_model:
        raise ValueError("candidate_model is required for live corpus mode")
    resolved = _resolve_live_session_ids(conn, session_ids)
    if len(resolved) > CORPUS_MAX_SESSIONS:
        raise ValueError(
            f"session_ids exceeds cap of {CORPUS_MAX_SESSIONS} — "
            "pass a smaller bounded list"
        )
    if not resolved:
        raise ValueError("no replayable sessions found for live corpus")

    verdicts: list[dict[str, Any]] = []
    total = len(resolved)
    for index, session_id in enumerate(resolved):
        session = repository.get_session(conn, session_id)
        if session is None:
            continue
        if not session.get("transcript"):
            continue
        replay_id = (new_replay_id or (lambda i=index: f"r_corpus_{i}"))()
        if progress:
            progress("replaying", index + 1, total)
        runs, verdict, duration_ms = await execute_replay(
            replay_id=replay_id,
            session=session,
            candidate_model=candidate_model,
            candidate_prompt=None,
            progress=None,
        )
        repository.insert_replay(
            conn,
            {
                "replay_id": replay_id,
                "session_id": session_id,
                "candidate_model": candidate_model,
                "candidate_prompt_ref": None,
                "runs": runs,
                "verdict": verdict,
                "duration_ms": duration_ms,
            },
        )
        verdicts.append(verdict)

    out = _aggregate_verdicts(verdicts, mode="live")
    out["requested_session_ids"] = resolved
    out["candidate_model"] = candidate_model
    out["sessions_replayed"] = len(verdicts)
    return out
