#!/usr/bin/env python3
"""Seed Griffin metric history (docs/07) — warm MAD bands before S4.

Writes data/griffin_series.json with ≥30 points per allowlisted series,
plus an optional end spike for Worms choreography testing.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWLIST = [
    "arcnet.tokens.total|agent_j",
    "arcnet.cost.usd|agent_j",
    "arcnet.tool.calls|agent_j",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Griffin series history")
    parser.add_argument("--points", type=int, default=60, help="history length (≥30 warm)")
    parser.add_argument("--spike", action="store_true", help="append a token-rate spike for S4")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "griffin_series.json",
    )
    args = parser.parse_args()

    rng = random.Random(42)
    now = time.time()
    series: dict[str, list[dict[str, float]]] = {}
    baselines = {
        "arcnet.tokens.total|agent_j": 120.0,
        "arcnet.cost.usd|agent_j": 0.002,
        "arcnet.tool.calls|agent_j": 3.0,
    }
    for sid in ALLOWLIST:
        base = baselines.get(sid, 10.0)
        pts: list[dict[str, float]] = []
        for i in range(args.points):
            wobble = 1.0 + 0.08 * math.sin(i / 7.0) + rng.uniform(-0.05, 0.05)
            pts.append({"t": now - (args.points - i) * 60.0, "v": max(0.0, base * wobble)})
        if args.spike and sid.startswith("arcnet.tokens.total"):
            pts.append({"t": now, "v": base * 25.0})
        series[sid] = pts

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(series, indent=2))
    print(f"seeded {args.out} series={list(series)} points={args.points} spike={args.spike}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
