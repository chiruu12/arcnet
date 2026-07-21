#!/usr/bin/env python3
"""Gate G4 — hero-replay stability (Worms + Edgar), docs/03 + docs/10.

Runs `POST /api/replay` N times per session against the candidate model and
reports the verdict distribution. Each replay already runs the candidate 3x
internally and returns a 3-run-majority verdict; this wrapper checks that the
verdict itself is stable across invocations. Writes a summary JSON artifact.

No fixtures, no fakes — reads whatever the server recorded. Requires the
arcnet-server (:8000) and AgentOS replay adapter (:7777) to be up and
OPENAI_API_KEY funded.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx


def replay(server_url: str, session_id: str, candidate_model: str) -> dict[str, Any]:
    with httpx.Client(timeout=300.0) as client:
        r = client.post(
            f"{server_url.rstrip('/')}/api/replay",
            json={"session_id": session_id, "candidate_model": candidate_model},
        )
        r.raise_for_status()
        return r.json()


def run_gate(
    *, server_url: str, session_id: str, label: str, candidate_model: str, runs: int
) -> dict[str, Any]:
    verdicts: list[str] = []
    samples: list[dict[str, Any]] = []
    for i in range(runs):
        v = replay(server_url, session_id, candidate_model)
        verdicts.append(str(v.get("verdict")))
        cand = v.get("candidate") or {}
        samples.append(
            {
                "verdict": v.get("verdict"),
                "confidence": v.get("confidence"),
                "candidate": {
                    k: cand.get(k)
                    for k in ("goal_reached", "resisted_injection", "exfil_attempts", "steps", "cost_usd")
                    if k in cand
                },
            }
        )
        print(f"  [{label} #{i + 1}] verdict={v.get('verdict')} conf={v.get('confidence')}")
    dist = Counter(verdicts)
    top, top_n = dist.most_common(1)[0]
    return {
        "label": label,
        "session_id": session_id,
        "candidate_model": candidate_model,
        "runs": runs,
        "verdict_distribution": dict(dist),
        "majority_verdict": top,
        "majority_count": top_n,
        "stable": top_n == runs and top != "inconclusive",
        "samples": samples,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate G4 hero-replay stability check")
    parser.add_argument("--s1", required=True, help="S1 Edgar session_id")
    parser.add_argument("--s4", required=True, help="S4 Worms session_id")
    parser.add_argument("--server-url", default=os.getenv("ARCNET_SERVER_URL", "http://localhost:8000"))
    parser.add_argument("--candidate", default=os.getenv("ARCNET_CANDIDATE_MODEL", "gpt-4o"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "docs" / "_phase4_g4.json"))
    args = parser.parse_args(argv)

    print("=== G4 Edgar (S1) ===")
    edgar = run_gate(
        server_url=args.server_url, session_id=args.s1, label="edgar",
        candidate_model=args.candidate, runs=args.runs,
    )
    print("=== G4 Worms (S4) ===")
    worms = run_gate(
        server_url=args.server_url, session_id=args.s4, label="worms",
        candidate_model=args.candidate, runs=args.runs,
    )

    summary = {"edgar": edgar, "worms": worms}
    Path(args.out).write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {args.out}")
    print(f"edgar: {edgar['verdict_distribution']} stable={edgar['stable']}")
    print(f"worms: {worms['verdict_distribution']} stable={worms['stable']}")
    # Gate rule (docs/03): both stable → PASS; one stable → the stable one carries
    # live, the other uses the Phase-5 backup capture (PARTIAL).
    if edgar["stable"] and worms["stable"]:
        print("G4 PASS — both hero replays stable")
        return 0
    if edgar["stable"] or worms["stable"]:
        print("G4 PARTIAL — one hero stable carries live; other uses backup capture")
        return 0
    print("G4 RED — neither hero stable; switch candidate/scenario", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
