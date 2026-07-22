"""Exploration-only model recommendations (Phase R3).

Never mutates live agents, posts kill/steer, or calls production control paths.
Catalog is a curated snapshot of current reliable OpenAI ids — not a live crawl
unless OPENAI_API_KEY is set and fetch_provider_catalog(live=True) is requested.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

TASK_TYPES: dict[str, dict[str, Any]] = {
    "tool_heavy": {
        "label": "Tool-heavy / loop-prone agents",
        "prefer": ["gpt-4o", "gpt-4.1", "o4-mini"],
        "avoid_hint": "avoid cheapest nano for long tool chains",
    },
    "injection_resist": {
        "label": "Forward-facing retrieval + side effects",
        "prefer": ["gpt-4o", "gpt-4.1", "o3-mini"],
        "avoid_hint": "prefer stronger instruction-following over cheapest batch",
    },
    "cheap_batch": {
        "label": "Cost-sensitive internal batch",
        "prefer": ["gpt-4o-mini", "gpt-4.1-mini", "o4-mini"],
        "avoid_hint": "reserve flagship models for contested incidents",
    },
    "long_context": {
        "label": "Large transcript / case-file analysis",
        "prefer": ["gpt-4.1", "gpt-4o", "o3-mini"],
        "avoid_hint": "check context window vs transcript size before switching",
    },
}

# Curated snapshot — update when provider lineup shifts (document in docs/log).
_OPENAI_SNAPSHOT: list[dict[str, Any]] = [
    {"id": "gpt-4o", "family": "gpt-4o", "tier": "reliable", "notes": "strong default candidate"},
    {"id": "gpt-4o-mini", "family": "gpt-4o", "tier": "cheap", "notes": "baseline / batch"},
    {"id": "gpt-4.1", "family": "gpt-4.1", "tier": "reliable", "notes": "long-context reliable"},
    {"id": "gpt-4.1-mini", "family": "gpt-4.1", "tier": "cheap", "notes": "cheaper 4.1"},
    {"id": "o4-mini", "family": "o-series", "tier": "reasoning", "notes": "tool-heavy reasoning"},
    {"id": "o3-mini", "family": "o-series", "tier": "reasoning", "notes": "stronger reasoning, higher cost"},
]


def list_task_types() -> list[dict[str, str]]:
    return [{"task_type": k, "label": v["label"]} for k, v in TASK_TYPES.items()]


def fetch_provider_catalog(
    provider: str = "openai",
    *,
    live: bool = False,
    max_models: int = 40,
) -> dict[str, Any]:
    """Return bounded model catalog. live=True hits OpenAI /v1/models (spend=0; list only)."""
    provider = provider.lower().strip()
    if provider != "openai":
        return {
            "provider": provider,
            "source": "unsupported",
            "models": [],
            "note": "only openai snapshot/live list supported in R3",
        }
    if not live:
        return {
            "provider": "openai",
            "source": "snapshot",
            "models": _OPENAI_SNAPSHOT[:max_models],
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return {
            "provider": "openai",
            "source": "snapshot_fallback",
            "models": _OPENAI_SNAPSHOT[:max_models],
            "note": "OPENAI_API_KEY empty — returned curated snapshot",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, dict):
                raise ValueError("models response is not an object")
            raw = payload.get("data") or []
            if not isinstance(raw, list):
                raise ValueError("models.data is not a list")
        # Prefer chat/reasoning-ish ids; keep list bounded
        ids = sorted(
            {
                m["id"]
                for m in raw
                if isinstance(m, dict)
                and isinstance(m.get("id"), str)
                and (
                    m["id"].startswith("gpt-")
                    or m["id"].startswith("o1")
                    or m["id"].startswith("o3")
                    or m["id"].startswith("o4")
                )
            }
        )[:max_models]
        return {
            "provider": "openai",
            "source": "openai_api",
            "models": [{"id": i} for i in ids],
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    except Exception as exc:  # noqa: BLE001 — any provider/network/parse miss → curated
        return {
            "provider": "openai",
            "source": "snapshot_fallback",
            "models": _OPENAI_SNAPSHOT[:max_models],
            "note": f"live catalog failed ({type(exc).__name__}); returned curated snapshot",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


_HERO_SESSIONS = ("s_ecfdb55d", "s_2af44726")


def _tm_evidence_for_recommend(
    *,
    session_id: str | None,
    server_url: str | None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Pull bounded TM verdict evidence for recommend reasons (never raises)."""
    refs: list[str] = []
    notes: list[dict[str, Any]] = []
    targets: list[str] = []
    if session_id and str(session_id).strip():
        targets.append(str(session_id).strip())
    else:
        targets.extend(_HERO_SESSIONS)
    for sid in targets[:3]:
        try:
            cmp = compare_replay_verdicts(sid, server_url=server_url)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(cmp, dict):
            continue
        for r in (cmp.get("evidence_refs") or [])[:4]:
            if isinstance(r, str) and r not in refs:
                refs.append(r)
        for row in (cmp.get("replays") or [])[:3]:
            if isinstance(row, dict):
                notes.append(
                    {
                        "session_id": sid,
                        "replay_id": row.get("replay_id"),
                        "candidate_model": row.get("candidate_model"),
                        "verdict": row.get("verdict"),
                    }
                )
        if refs:
            break
    return refs[:10], notes[:6]


def recommend_models(
    task_type: str,
    *,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rank candidates for a task type. Exploration only — no agent mutation.

    When ``constraints.live`` is True *or* omitted and ``OPENAI_API_KEY`` is set,
    prefer the live OpenAI model list (still exploration-only; never mutates agents).
    Provider/network/parse failures fall back to the curated snapshot instead of raising.
    Explicit ``live=False`` keeps the curated snapshot.

    When ``constraints.session_id`` is set (or hero replays are reachable), reasons
    cite Time Machine verdict evidence_refs.
    """
    constraints = constraints or {}
    meta = TASK_TYPES.get(task_type)
    if meta is None:
        return {
            "task_type": task_type,
            "recommendations": [],
            "error": f"unknown task_type; known={list(TASK_TYPES)}",
            "exploration_only": True,
        }
    live_flag = constraints.get("live")
    if live_flag is None:
        live = bool(os.getenv("OPENAI_API_KEY", "").strip())
    else:
        live = bool(live_flag)
    catalog = fetch_provider_catalog(
        constraints.get("provider") or "openai",
        live=live,
    )
    by_id = {
        m["id"]: m
        for m in catalog.get("models", [])
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    }
    max_cost = constraints.get("max_cost_usd")
    session_id = constraints.get("session_id")
    server_url = constraints.get("server_url")
    if isinstance(server_url, str):
        pass
    else:
        server_url = None
    tm_refs, tm_notes = _tm_evidence_for_recommend(
        session_id=str(session_id) if session_id else None,
        server_url=server_url,
    )
    # Rank models that won TM replays slightly higher when present
    tm_winners: set[str] = set()
    for n in tm_notes:
        mid = n.get("candidate_model")
        verd = str(n.get("verdict") or "").lower()
        if isinstance(mid, str) and verd in ("better", "win", "improved", "candidate_better"):
            tm_winners.add(mid)
    ranked: list[dict[str, Any]] = []
    for i, mid in enumerate(meta["prefer"]):
        # Prefer curated order; include even if live catalog omitted notes.
        if mid not in by_id and catalog.get("source") == "openai_api":
            # Still recommend known prefer ids; evidence notes catalog miss.
            pass
        if max_cost is not None and mid in ("o3-mini", "gpt-4.1") and float(max_cost) < 0.05:
            continue
        notes = by_id.get(mid, {}).get("notes") or (
            "in live catalog" if mid in by_id else "prefer list (may be newer than snapshot)"
        )
        reason = f"{meta['label']}: prefer {mid} ({notes})"
        evidence = [
            f"task_type:{task_type}",
            f"catalog:{catalog.get('source')}",
            f"in_catalog:{mid in by_id}",
        ]
        if mid in tm_winners:
            reason += " · TM verdict favors this candidate on stored replays"
            evidence.append(f"tm_winner:{mid}")
        for ref in tm_refs:
            if ref not in evidence:
                evidence.append(ref)
        ranked.append(
            {
                "model": mid,
                "rank": i + 1,
                "reason": reason,
                "evidence_refs": evidence[:12],
            }
        )
    # Promote TM winners within the list (stable otherwise)
    if tm_winners:
        ranked.sort(key=lambda r: (0 if r["model"] in tm_winners else 1, r["rank"]))
        for i, row in enumerate(ranked):
            row["rank"] = i + 1
    return {
        "task_type": task_type,
        "constraints": {**constraints, "live_resolved": live},
        "catalog_source": catalog.get("source"),
        "recommendations": ranked,
        "avoid_hint": meta["avoid_hint"],
        "tm_evidence": tm_notes,
        "exploration_only": True,
    }


def compare_replay_verdicts(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Summarize Time Machine verdicts for a session (bounded; via ArcNet API).

    Always includes ``evidence_refs`` citing replay_ids and dimension winners.
    Network failures return a structured error dict (never raise into callers).
    """
    from arcnet.hq import _base

    base = _base(server_url)
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                f"{base}/api/replays",
                params={"session_id": session_id, "limit": 20},
            )
            r.raise_for_status()
            rows = r.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": "replays_fetch_failed",
            "session_id": session_id,
            "detail": str(exc)[:300],
            "evidence_refs": [],
            "replays": [],
            "exploration_only": True,
        }
    if not isinstance(rows, list):
        rows = []
    summaries: list[dict[str, Any]] = []
    evidence_refs: list[str] = [f"session:{session_id}"]
    dim_winners: dict[str, str] = {}
    for row in rows[:10]:
        v = row.get("verdict") if isinstance(row, dict) else None
        if not isinstance(v, dict):
            continue
        rid = row.get("replay_id")
        cand = row.get("candidate_model")
        if rid:
            evidence_refs.append(f"replay:{rid}")
        if cand:
            evidence_refs.append(f"candidate_model:{cand}")
        cand_m = v.get("candidate") if isinstance(v.get("candidate"), dict) else {}
        base_m = v.get("baseline") if isinstance(v.get("baseline"), dict) else {}
        for dim in ("resisted_injection", "goal_reached", "cost_usd", "tool_errors"):
            if dim not in cand_m and dim not in base_m:
                continue
            c_val = cand_m.get(dim)
            b_val = base_m.get(dim)
            winner = None
            if isinstance(c_val, bool) and isinstance(b_val, bool):
                if c_val and not b_val:
                    winner = str(cand or "candidate")
                elif b_val and not c_val:
                    winner = str(base_m.get("model") or "baseline")
            elif isinstance(c_val, (int, float)) and isinstance(b_val, (int, float)):
                # Lower cost / tool_errors is better
                if dim in ("cost_usd", "tool_errors"):
                    winner = str(cand or "candidate") if c_val <= b_val else str(
                        base_m.get("model") or "baseline"
                    )
                else:
                    winner = str(cand or "candidate") if c_val >= b_val else str(
                        base_m.get("model") or "baseline"
                    )
            if winner:
                dim_winners[dim] = winner
                evidence_refs.append(f"dim:{dim}:{winner}")
        summaries.append(
            {
                "replay_id": rid,
                "candidate_model": cand,
                "verdict": v.get("verdict"),
                "confidence": v.get("confidence"),
                "recommendation": (v.get("recommendation") or "")[:240],
                "baseline_model": base_m.get("model"),
                "candidate_metrics": {
                    k: cand_m.get(k)
                    for k in (
                        "goal_reached",
                        "resisted_injection",
                        "cost_usd",
                        "steps",
                        "tool_errors",
                    )
                    if k in cand_m
                },
            }
        )
    # Dedupe evidence
    seen: set[str] = set()
    refs_out: list[str] = []
    for r in evidence_refs:
        s = str(r)[:160]
        if s not in seen:
            seen.add(s)
            refs_out.append(s)
        if len(refs_out) >= 16:
            break
    return {
        "ok": True,
        "session_id": session_id,
        "replays": summaries,
        "dimension_winners": dim_winners,
        "evidence_refs": refs_out,
        "truncated": len(rows) > 10,
        "exploration_only": True,
    }


def record_recommendation_note(
    *,
    task_type: str,
    recommendations: list[dict[str, Any]],
    out_dir: str | Path | None = None,
    server_url: str | None = None,
    post_signal: bool = False,
) -> dict[str, Any]:
    """Persist a local exploration note (not a kill/steer signal).

    Optional ``post_signal=True`` writes ``kind=note`` ``source=model_explorer``
    via ArcNet API — still never calls apply/kill.
    """
    root = Path(out_dir or os.getenv("ARCNET_EXPLORE_DIR") or "data/model_explore")
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = root / f"rec_{task_type}_{stamp}.json"
    payload = {
        "kind": "note",
        "source": "model_explorer",
        "task_type": task_type,
        "recommendations": recommendations,
        "created_at": stamp,
        "exploration_only": True,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    out: dict[str, Any] = {"path": str(path), "note": payload}
    if post_signal:
        from arcnet.hq import _base

        top = recommendations[0] if recommendations else {}
        reason = (
            f"model_explorer recommend {task_type}: "
            f"{top.get('model', '?')} — {(top.get('reason') or '')[:200]}"
        )
        try:
            with httpx.Client(timeout=8.0) as client:
                r = client.post(
                    f"{_base(server_url)}/api/signal",
                    json={
                        "agent_id": "model_explorer",
                        "kind": "note",
                        "severity": "info",
                        "reason": reason[:500],
                        "guidance": (
                            "Exploration only — never auto-apply. "
                            f"evidence_refs={top.get('evidence_refs', [])[:6]}"
                        )[:800],
                        "source": "model_explorer",
                    },
                )
                r.raise_for_status()
                out["signal"] = r.json()
        except Exception as exc:  # noqa: BLE001
            out["signal_error"] = str(exc)[:300]
    return out


def maybe_run_explore_loop(
    *,
    task_types: list[str] | None = None,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Optional explore loop behind ``ARCNET_MODEL_EXPLORE_LOOP=1``.

    recommend + record note only — **never** apply/kill. No-op when env unset.
    """
    if os.getenv("ARCNET_MODEL_EXPLORE_LOOP", "").strip() not in ("1", "true", "yes"):
        return {
            "ran": False,
            "reason": "ARCNET_MODEL_EXPLORE_LOOP not enabled",
            "exploration_only": True,
        }
    types = task_types or list(TASK_TYPES.keys())
    results: list[dict[str, Any]] = []
    for tt in types:
        rec = recommend_models(tt, constraints={"server_url": server_url})
        note = record_recommendation_note(
            task_type=tt,
            recommendations=rec.get("recommendations") or [],
            server_url=server_url,
            post_signal=True,
        )
        results.append({"task_type": tt, "recommend": rec, "note": note})
    return {
        "ran": True,
        "results": results,
        "exploration_only": True,
        "note": "recommend+record only — never apply/kill",
    }
