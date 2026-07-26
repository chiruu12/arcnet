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
        "prefer": ["gpt-5.6-terra", "gpt-5.6-luna", "kimi-k2.7-code", "claude-sonnet-4-6"],
        "avoid_hint": "avoid cheapest nano/flash for long tool chains",
    },
    "injection_resist": {
        "label": "Forward-facing retrieval + side effects",
        "prefer": ["gpt-5.6-terra", "claude-sonnet-4-6", "gpt-5.6-sol", "grok-4.5"],
        "avoid_hint": "prefer stronger instruction-following over cheapest batch",
    },
    "cheap_batch": {
        "label": "Cost-sensitive internal batch",
        "prefer": ["gpt-5.6-luna", "deepseek-v4-flash", "claude-haiku-4-5", "gemini-3-flash"],
        "avoid_hint": "reserve frontier models for contested incidents",
    },
    "long_context": {
        "label": "Large transcript / case-file analysis",
        "prefer": ["kimi-k2.7-code", "kimi-k3", "gpt-5.6-luna", "claude-sonnet-4-6", "qwen3.8-max-preview", "gemini-3.1-pro"],
        "avoid_hint": "check context window vs transcript size before switching",
    },
}

# Offline fallback when ArcNet server catalog is unreachable.
_OPENAI_SNAPSHOT: list[dict[str, Any]] = [
    {"id": "gpt-5.6-luna", "family": "gpt-5.6", "tier": "mid", "notes": "cost-optimized fleet baseline"},
    {"id": "gpt-5.6-terra", "family": "gpt-5.6", "tier": "high", "notes": "balanced professional tier"},
    {"id": "gpt-5.6-sol", "family": "gpt-5.6", "tier": "frontier", "notes": "frontier reasoning"},
    {"id": "claude-sonnet-4-6", "family": "claude", "tier": "high", "notes": "proven Sonnet tier"},
    {"id": "claude-opus-5", "family": "claude", "tier": "frontier", "notes": "frontier anthropic"},
    {"id": "kimi-k2.7-code", "family": "kimi", "tier": "high", "notes": "verified open-weight coding"},
    {"id": "kimi-k3", "family": "kimi", "tier": "high", "notes": "API preview — prefer k2.7-code for weights"},
    {"id": "qwen3.8-max-preview", "family": "qwen", "tier": "frontier", "notes": "Alibaba preview flagship"},
    {"id": "qwen3.6-35b-a3b", "family": "qwen", "tier": "high", "notes": "verified Apache-2.0 open-weight"},
    {"id": "deepseek-v4-flash", "family": "deepseek", "tier": "light", "notes": "cheapest throughput"},
    {"id": "deepseek-v4-pro", "family": "deepseek", "tier": "high", "notes": "open-weight SOTA coding efficiency"},
]


def fetch_arcnet_catalog(
    *,
    server_url: str | None = None,
    provider: str | None = None,
    status: str | None = None,
    capability_tier: str | None = None,
    min_context: int | None = None,
    reasoning: bool | None = None,
) -> dict[str, Any]:
    """Fetch GET /api/models/catalog with snapshot fallback."""
    from arcnet.hq import _base

    base = _base(server_url)
    params: dict[str, Any] = {}
    if provider:
        params["provider"] = provider
    if status:
        params["status"] = status
    if capability_tier:
        params["capability_tier"] = capability_tier
    if min_context is not None:
        params["min_context"] = min_context
    if reasoning is not None:
        params["reasoning"] = reasoning
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{base}/api/models/catalog", params=params or None)
            r.raise_for_status()
            payload = r.json()
        if isinstance(payload, dict) and isinstance(payload.get("models"), list):
            return {
                "source": "arcnet_api",
                "catalog_version": payload.get("catalog_version"),
                "models": payload["models"],
                "count": payload.get("count", len(payload["models"])),
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
    except Exception as exc:  # noqa: BLE001
        fallback_note = f"arcnet catalog fetch failed ({type(exc).__name__}); snapshot fallback"
    else:
        fallback_note = None
    models = [
        {"id": m["id"], "provider": "openai", "capability_tier": m.get("tier"), **m}
        for m in _OPENAI_SNAPSHOT
    ]
    return {
        "source": "snapshot_fallback",
        "catalog_version": "offline",
        "models": models,
        "count": len(models),
        "note": fallback_note,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


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

    When ``constraints.session_id`` is set, reasons cite that session's Time Machine
    verdicts and winners may reorder the curated list. Without a session_id, hero
    sessions may appear as optional evidence citations only — they never promote
    ranking across unrelated task types.
    """
    constraints = constraints or {}
    meta = TASK_TYPES.get(task_type)
    if meta is None:
        return {
            "task_type": task_type,
            "recommendations": [],
            "evidence_refs": [],
            "evidence_refs_empty_reason": (
                f"unknown task_type; known={list(TASK_TYPES)}"
            ),
            "error": f"unknown task_type; known={list(TASK_TYPES)}",
            "exploration_only": True,
        }
    live_flag = constraints.get("live")
    server_url = constraints.get("server_url")
    arcnet_catalog = fetch_arcnet_catalog(server_url=server_url if isinstance(server_url, str) else None)
    if live_flag is None:
        live = bool(os.getenv("OPENAI_API_KEY", "").strip())
    else:
        live = bool(live_flag)
    catalog = fetch_provider_catalog(
        constraints.get("provider") or "openai",
        live=live,
    )
    # Merge ArcNet catalog ids into lookup for prefer-list validation.
    arcnet_by_id = {
        m["id"]: m
        for m in arcnet_catalog.get("models", [])
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    }
    by_id = {
        m["id"]: m
        for m in catalog.get("models", [])
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    }
    by_id.update(arcnet_by_id)
    max_cost = constraints.get("max_cost_usd")
    session_id = constraints.get("session_id")
    if isinstance(server_url, str):
        pass
    else:
        server_url = None
    scoped_session = bool(session_id and str(session_id).strip())
    # Without a session_id, skip TM entirely so hero wins cannot reshape ranking
    if scoped_session:
        tm_refs, tm_notes = _tm_evidence_for_recommend(
            session_id=str(session_id).strip(),
            server_url=server_url,
        )
    else:
        tm_refs, tm_notes = [], []
    # Only promote winners from the caller's session
    tm_winners: set[str] = set()
    for n in tm_notes:
        mid = n.get("candidate_model")
        verd = str(n.get("verdict") or "").lower()
        if isinstance(mid, str) and verd in (
            "better",
            "win",
            "improved",
            "candidate_better",
        ):
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
    # Promote TM winners within the list only for the caller's session
    if tm_winners:
        ranked.sort(key=lambda r: (0 if r["model"] in tm_winners else 1, r["rank"]))
        for i, row in enumerate(ranked):
            row["rank"] = i + 1
    out: dict[str, Any] = {
        "task_type": task_type,
        "constraints": {**constraints, "live_resolved": live},
        "catalog_source": catalog.get("source"),
        "arcnet_catalog_source": arcnet_catalog.get("source"),
        "arcnet_catalog_version": arcnet_catalog.get("catalog_version"),
        "recommendations": ranked,
        "avoid_hint": meta["avoid_hint"],
        "tm_evidence": tm_notes,
        "exploration_only": True,
    }
    # Top-level evidence_refs always present (union of row refs, or empty reason).
    top_refs: list[str] = []
    seen: set[str] = set()
    for row in ranked:
        for r in row.get("evidence_refs") or []:
            s = str(r)
            if s not in seen:
                seen.add(s)
                top_refs.append(s)
            if len(top_refs) >= 12:
                break
        if len(top_refs) >= 12:
            break
    out["evidence_refs"] = top_refs
    if not top_refs:
        out["evidence_refs_empty_reason"] = (
            "no recommendations after prefer-list / cost filters"
            if not ranked
            else "recommendations present but no evidence_refs collected"
        )
    return out


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
    # Majority vote per dimension (ties keep first-seen) — never last-write-wins
    dim_votes: dict[str, dict[str, int]] = {}
    dim_first: dict[str, str] = {}
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
        per_replay: dict[str, str] = {}
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
                votes = dim_votes.setdefault(dim, {})
                votes[winner] = votes.get(winner, 0) + 1
                dim_first.setdefault(dim, winner)
                per_replay[dim] = winner
                tag = f"dim:{dim}:{winner}"
                if rid:
                    tag = f"{tag}:replay:{rid}"
                evidence_refs.append(tag)
        summaries.append(
            {
                "replay_id": rid,
                "candidate_model": cand,
                "verdict": v.get("verdict"),
                "confidence": v.get("confidence"),
                "recommendation": (v.get("recommendation") or "")[:240],
                "baseline_model": base_m.get("model"),
                "dimension_winners": per_replay,
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
    dim_winners: dict[str, str] = {}
    for dim, votes in dim_votes.items():
        # Highest vote count; ties keep first-seen winner for that dimension
        best = max(
            votes.items(),
            key=lambda kv: (kv[1], 1 if kv[0] == dim_first.get(dim) else 0),
        )[0]
        dim_winners[dim] = best
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
