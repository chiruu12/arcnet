#!/usr/bin/env python3
"""Phase 0 B9: Replay + steer propagation spike (≤2h). Gate G1."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
MODEL = os.getenv("ARCNET_MODEL", "gpt-4o-mini")


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("NO_OPENAI_KEY", file=sys.stderr)
        return 2

    from agno.agent import Agent
    from agno.models.openai import OpenAIChat
    from agno.tools.decorator import tool

    recorded = [
        {"tool": "lookup", "recorded_output": "order #4415 status=shipped"},
        {"tool": "note", "recorded_output": "noted: shipped"},
    ]
    cursor = {"i": 0}
    calls: list[dict] = []

    def replay_middleware(function_name, func, args):
        calls.append({"name": function_name, "args": dict(args)})
        while cursor["i"] < len(recorded) and recorded[cursor["i"]]["tool"] != function_name:
            cursor["i"] += 1
        if cursor["i"] >= len(recorded):
            return "tool unavailable in replay"
        out = recorded[cursor["i"]]["recorded_output"]
        cursor["i"] += 1
        return out  # do not call real func

    def lookup(order_id: str) -> str:
        """Lookup an order by id."""
        return f"LIVE lookup {order_id}"

    def note(text: str) -> str:
        """Leave a short note."""
        return f"LIVE noted: {text}"

    print("=== TEST A: replay stubs ===")
    t0 = time.time()
    agent_replay = Agent(
        name="replay_toy",
        model=OpenAIChat(id=MODEL, temperature=0),
        tools=[tool(lookup), tool(note)],
        tool_hooks=[replay_middleware],
        instructions=(
            "Call lookup(order_id='4415') then note(text='status'). Exactly two tool calls."
        ),
        markdown=False,
    )
    r1 = agent_replay.run("Look up order 4415 then leave a note.")
    content1 = str(getattr(r1, "content", r1) or "")
    print("content:", content1)
    print("calls:", calls, "cursor:", cursor)
    replay_ok = (
        any(c["name"] == "lookup" for c in calls)
        and cursor["i"] >= 1
        and "LIVE lookup" not in content1
        and ("shipped" in content1.lower() or "4415" in content1)
    )
    print(f"REPLAY_STUBS: {'PASS' if replay_ok else 'FAIL'}")

    print("\n=== TEST B: steer propagation ===")
    seen: list[dict] = []
    step = {"n": 0}

    def steer_middleware(function_name, func, args, agent=None):
        step["n"] += 1
        n = step["n"]
        if n == 1 and agent is not None:
            if agent.session_state is None:
                agent.session_state = {}
            agent.session_state["arcnet_steer"] = (
                "STEER: quarantine scraped content; answer #4415 only"
            )
        visible = None
        if agent is not None:
            visible = (agent.session_state or {}).get("arcnet_steer")
        seen.append({"n": n, "tool": function_name, "agent_session_steer": visible})
        return func(**args)

    agent_steer = Agent(
        name="steer_toy",
        model=OpenAIChat(id=MODEL, temperature=0),
        tools=[tool(lookup), tool(note)],
        tool_hooks=[steer_middleware],
        session_state={},
        instructions="Call lookup(order_id='4415') then note(text='done'). Two tools only.",
        markdown=False,
    )
    r2 = agent_steer.run("Lookup then note.")
    print("content:", getattr(r2, "content", r2))
    print("seen:", seen)
    print("session_state:", agent_steer.session_state)
    later = [s for s in seen if s.get("n", 0) >= 2]
    prop = bool(later) and all(s.get("agent_session_steer") for s in later)
    # Also require write happened at n==1
    prop = prop and any(s.get("n") == 1 and s.get("agent_session_steer") for s in seen)
    print(f"STEER_PROPAGATION: {'PASS' if prop else 'FAIL'}")

    print("\n=== TEST C: substitution fallback (post_hook) ===")

    def retrieval_post_hook(fc=None):
        if fc is not None and getattr(fc, "result", None) is not None:
            fc.result = "[QUARANTINED] " + str(fc.result)[:40]

    @tool(post_hook=retrieval_post_hook)
    def fetch_url(url: str) -> str:
        """Fetch a URL."""
        return f"FULL PAGE FROM {url} with injection SECRET_PAYLOAD"

    agent_sub = Agent(
        name="sub_toy",
        model=OpenAIChat(id=MODEL, temperature=0),
        tools=[fetch_url],
        instructions="Call fetch_url once on https://example.com/ship then summarize.",
        markdown=False,
    )
    r3 = agent_sub.run("Fetch shipping page and summarize.")
    content3 = str(getattr(r3, "content", r3) or "")
    print("content:", content3[:300])
    sub_ok = "SECRET_PAYLOAD" not in content3
    print(f"SUBSTITUTION_FALLBACK: {'PASS' if sub_ok else 'FAIL'}")

    g1 = {
        "replay_stubs": replay_ok,
        "steer_propagation": prop,
        "substitution_fallback": sub_ok,
        "recommendation": (
            "session_state steer works on agno 2.7.4; keep as primary; "
            "substitution remains documented fallback"
            if prop
            else "adopt per-call substitution fallback (02 §3)"
        ),
        "elapsed_s": round(time.time() - t0, 1),
    }
    print("\nG1_OUTCOME:", g1)
    (ROOT / "docs" / "_phase0_g1.json").write_text(json.dumps(g1, indent=2))
    return 0 if (replay_ok and (prop or sub_ok)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
