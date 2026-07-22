#!/usr/bin/env python3
"""Minimal stdio MCP-shaped shim for ArcNet model-explore tools.

Not a full MCP SDK server — prints JSON-RPC-ish request/response over stdin/stdout
for coding agents that can invoke tools by name. Prefer importing
`arcnet.model_explore` directly when in-process.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from arcnet.model_explore import (
    compare_replay_verdicts,
    fetch_provider_catalog,
    list_task_types,
    recommend_models,
)


def _handle(name: str, args: dict[str, Any]) -> Any:
    if name == "list_task_types":
        return list_task_types()
    if name == "recommend_models":
        return recommend_models(args["task_type"], constraints=args.get("constraints"))
    if name == "compare_replay_verdicts":
        return compare_replay_verdicts(args["session_id"], server_url=args.get("server_url"))
    if name == "fetch_provider_catalog":
        return fetch_provider_catalog(
            args.get("provider") or "openai",
            live=bool(args.get("live")),
        )
    raise ValueError(f"unknown tool {name}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            name = req.get("tool") or req.get("name")
            args = req.get("arguments") or req.get("args") or {}
            result = _handle(str(name), args if isinstance(args, dict) else {})
            sys.stdout.write(json.dumps({"ok": True, "result": result}) + "\n")
        except Exception as exc:  # noqa: BLE001
            sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
