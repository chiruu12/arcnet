#!/usr/bin/env python3
"""Stdio MCP server for ArcNet model-explore tools.

Speaks JSON-RPC 2.0 over stdin/stdout (one message per line) so Cursor/Claude
can initialize, list tools, and call them. Prefer importing
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

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_task_types",
        "description": "List known ArcNet model-explore task type buckets.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "recommend_models",
        "description": "Rank candidate models for a task type (exploration only).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string"},
                "constraints": {"type": "object"},
            },
            "required": ["task_type"],
            "additionalProperties": False,
        },
    },
    {
        "name": "compare_replay_verdicts",
        "description": "Summarize Time Machine verdict winners for a session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "server_url": {"type": "string"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fetch_provider_catalog",
        "description": "Bounded OpenAI model catalog (snapshot by default).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "live": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    },
]


def _handle_tool(name: str, args: dict[str, Any]) -> Any:
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


def _rpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _dispatch(req: dict[str, Any]) -> dict[str, Any] | None:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") if isinstance(req.get("params"), dict) else {}

    # Legacy shim: {"tool"|"name", "arguments"|"args"} without method
    if method is None and (req.get("tool") or req.get("name")):
        name = str(req.get("tool") or req.get("name"))
        args = req.get("arguments") or req.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        try:
            result = _handle_tool(name, args)
            if req_id is None:
                return {"ok": True, "result": result}
            return _rpc_result(req_id, {"content": [{"type": "text", "text": json.dumps(result)}]})
        except Exception as exc:  # noqa: BLE001
            if req_id is None:
                return {"ok": False, "error": str(exc)}
            return _rpc_error(req_id, -32000, str(exc))

    if method == "initialize":
        return _rpc_result(
            req_id,
            {
                "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "arcnet-model-explore", "version": "0.1.0"},
            },
        )

    if method == "notifications/initialized" or method == "initialized":
        return None  # notification — no response

    if method == "ping":
        return _rpc_result(req_id, {})

    if method == "tools/list":
        return _rpc_result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        try:
            result = _handle_tool(name, args)
            return _rpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "isError": False,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return _rpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            )

    if method is None:
        return _rpc_error(req_id, -32600, "invalid request: missing method")
    return _rpc_error(req_id, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if not isinstance(req, dict):
                sys.stdout.write(
                    json.dumps(_rpc_error(None, -32600, "request must be a JSON object")) + "\n"
                )
            else:
                resp = _dispatch(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp) + "\n")
        except json.JSONDecodeError as exc:
            sys.stdout.write(json.dumps(_rpc_error(None, -32700, f"parse error: {exc}")) + "\n")
        except Exception as exc:  # noqa: BLE001
            sys.stdout.write(json.dumps(_rpc_error(None, -32603, str(exc))) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
