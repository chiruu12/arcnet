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
    with httpx.Client(timeout=15.0) as client:
        r = client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        r.raise_for_status()
        raw = r.json().get("data") or []
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


def recommend_models(
    task_type: str,
    *,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rank candidates for a task type. Exploration only — no agent mutation.

    When ``constraints.live`` is True *or* omitted and ``OPENAI_API_KEY`` is set,
    prefer the live OpenAI model list (still exploration-only; never mutates agents).
    Explicit ``live=False`` keeps the curated snapshot.
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
        ranked.append(
            {
                "model": mid,
                "rank": i + 1,
                "reason": f"{meta['label']}: prefer {mid} ({notes})",
                "evidence_refs": [
                    f"task_type:{task_type}",
                    f"catalog:{catalog.get('source')}",
                    f"in_catalog:{mid in by_id}",
                ],
            }
        )
    return {
        "task_type": task_type,
        "constraints": {**constraints, "live_resolved": live},
        "catalog_source": catalog.get("source"),
        "recommendations": ranked,
        "avoid_hint": meta["avoid_hint"],
        "exploration_only": True,
    }


def compare_replay_verdicts(
    session_id: str,
    *,
    server_url: str | None = None,
) -> dict[str, Any]:
    """Summarize Time Machine verdicts for a session (bounded; via ArcNet API)."""
    from arcnet.hq import _base

    base = _base(server_url)
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{base}/api/replays", params={"session_id": session_id, "limit": 20})
        r.raise_for_status()
        rows = r.json()
    summaries: list[dict[str, Any]] = []
    for row in rows[:10]:
        v = row.get("verdict") if isinstance(row, dict) else None
        if not isinstance(v, dict):
            continue
        summaries.append(
            {
                "replay_id": row.get("replay_id"),
                "candidate_model": row.get("candidate_model"),
                "verdict": v.get("verdict"),
                "confidence": v.get("confidence"),
                "recommendation": (v.get("recommendation") or "")[:240],
                "baseline_model": (v.get("baseline") or {}).get("model"),
                "candidate_metrics": {
                    k: (v.get("candidate") or {}).get(k)
                    for k in (
                        "goal_reached",
                        "resisted_injection",
                        "cost_usd",
                        "steps",
                        "tool_errors",
                    )
                    if k in (v.get("candidate") or {})
                },
            }
        )
    return {
        "session_id": session_id,
        "replays": summaries,
        "truncated": len(rows) > 10,
        "exploration_only": True,
    }


def record_recommendation_note(
    *,
    task_type: str,
    recommendations: list[dict[str, Any]],
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Persist a local exploration note (not a kill/steer signal)."""
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
    return {"path": str(path), "note": payload}
