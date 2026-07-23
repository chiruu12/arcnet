#!/usr/bin/env python3
"""Stdio MCP server for ArcNet HQ Agent tools (JSON-RPC 2.0)."""

from __future__ import annotations

import json
import sys
from typing import Any

from arcnet import hq_tools

TOOLS: list[dict[str, Any]] = [
    {
        "name": "signoz_status",
        "description": "ArcNet SigNoz probe: UI, API key, query_range, dashboard UUIDs.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "signoz_evidence",
        "description": "Bounded SigNoz HTTP/Query Range evidence (prefer over MCP; span names/ids only).",
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
        "name": "fleet_overview",
        "description": "Fleet health rows from ArcNet server.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "agent_signals",
        "description": "Bounded signals envelope for agent_id or session_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_or_session_id": {"type": "string"},
                "server_url": {"type": "string"},
            },
            "required": ["agent_or_session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "session_check",
        "description": "Compact session diagnosis (no full tool outputs).",
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
        "name": "case_file_view",
        "description": "Bounded Case File / incident envelope for a session.",
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
        "name": "replay_compare",
        "description": "Bounded Time Machine verdict summaries for a session.",
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
        "name": "griffin_anomalies",
        "description": "Griffin MAD anomaly cache + recent griffin signals.",
        "inputSchema": {
            "type": "object",
            "properties": {"server_url": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    {
        "name": "list_agent_models",
        "description": "Models observed for an agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "server_url": {"type": "string"},
            },
            "required": ["agent_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "recommend_models",
        "description": "Exploration-only model ranking for a task type.",
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
        "name": "agent_version_timeline",
        "description": "Registered agent version timeline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "server_url": {"type": "string"},
            },
            "required": ["agent_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "register_agent_version",
        "description": "Register a deployed agent version after a real change.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "version": {"type": "string"},
                "model": {"type": "string"},
                "model_version": {"type": "string"},
                "source_ref": {"type": "string"},
                "notes": {"type": "string"},
                "session_id": {"type": "string"},
                "server_url": {"type": "string"},
            },
            "required": ["agent_id", "version"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_model_change",
        "description": "Record a model-change proposal note (does not auto-apply).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "to_model": {"type": "string"},
                "reason": {"type": "string"},
                "from_model": {"type": "string"},
                "task_type": {"type": "string"},
                "session_id": {"type": "string"},
                "server_url": {"type": "string"},
            },
            "required": ["agent_id", "to_model", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_model_proposals",
        "description": "List recent hq_agent proposal notes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "server_url": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "apply_model_change",
        "description": "Human-gated model apply. Requires confirm=true; records version bump. Sets agentos_reload_required.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "model": {"type": "string"},
                "version": {"type": "string"},
                "confirm": {"type": "boolean"},
                "session_id": {"type": "string"},
                "proposal_signal_id": {"type": "string"},
                "notes": {"type": "string"},
                "server_url": {"type": "string"},
            },
            "required": ["agent_id", "model", "version", "confirm"],
            "additionalProperties": False,
        },
    },
]


def _handle_tool(name: str, args: dict[str, Any]) -> Any:
    server_url = args.get("server_url")
    if name == "signoz_status":
        return hq_tools.signoz_status(server_url=server_url)
    if name == "signoz_evidence":
        return hq_tools.signoz_evidence(args["session_id"], server_url=server_url)
    if name == "fleet_overview":
        return hq_tools.fleet_overview(server_url=server_url)
    if name == "agent_signals":
        return hq_tools.agent_signals(args["agent_or_session_id"], server_url=server_url)
    if name == "session_check":
        return hq_tools.session_check(args["session_id"], server_url=server_url)
    if name == "case_file_view":
        return hq_tools.case_file_view(args["session_id"], server_url=server_url)
    if name == "replay_compare":
        return hq_tools.replay_compare(args["session_id"], server_url=server_url)
    if name == "griffin_anomalies":
        return hq_tools.griffin_anomalies(server_url=server_url)
    if name == "list_agent_models":
        return hq_tools.list_agent_models(args["agent_id"], server_url=server_url)
    if name == "recommend_models":
        return hq_tools.recommend_models(args["task_type"], constraints=args.get("constraints"))
    if name == "agent_version_timeline":
        return hq_tools.agent_version_timeline(args["agent_id"], server_url=server_url)
    if name == "register_agent_version":
        return hq_tools.register_agent_version(
            args["agent_id"],
            args["version"],
            model=args.get("model"),
            model_version=args.get("model_version"),
            source_ref=args.get("source_ref"),
            notes=args.get("notes"),
            session_id=args.get("session_id"),
            server_url=server_url,
        )
    if name == "propose_model_change":
        return hq_tools.propose_model_change(
            args["agent_id"],
            args["to_model"],
            args["reason"],
            from_model=args.get("from_model"),
            task_type=args.get("task_type"),
            session_id=args.get("session_id"),
            server_url=server_url,
        )
    if name == "list_model_proposals":
        return hq_tools.list_model_proposals(
            agent_id=args.get("agent_id"),
            server_url=server_url,
        )
    if name == "apply_model_change":
        return hq_tools.apply_model_change(
            args["agent_id"],
            args["model"],
            args["version"],
            confirm=bool(args.get("confirm")),
            session_id=args.get("session_id"),
            proposal_signal_id=args.get("proposal_signal_id"),
            notes=args.get("notes"),
            server_url=server_url,
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
                "serverInfo": {"name": "arcnet-hq-agent", "version": "0.1.0"},
            },
        )

    if method in ("notifications/initialized", "initialized"):
        return None

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
                {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False},
            )
        except Exception as exc:  # noqa: BLE001
            return _rpc_result(
                req_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
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
