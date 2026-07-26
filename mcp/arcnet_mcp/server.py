"""ArcNet MCP stdio server entrypoint."""

from __future__ import annotations

import asyncio
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from arcnet_mcp import tools

app = Server("arcnet")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="arcnet_fleet_health",
            description="Fleet health envelope (agent-view twin)",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="arcnet_search_threats",
            description="Paginated threats by agent_id or session_id",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "session_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        Tool(
            name="arcnet_get_incident",
            description="Incident envelope for a session",
            inputSchema={
                "type": "object",
                "required": ["session_id"],
                "properties": {"session_id": {"type": "string"}},
            },
        ),
        Tool(
            name="arcnet_case_file",
            description="Case file agent-view for a session",
            inputSchema={
                "type": "object",
                "required": ["session_id"],
                "properties": {"session_id": {"type": "string"}},
            },
        ),
        Tool(
            name="arcnet_replay_verdicts",
            description="Time Machine verdicts for a session",
            inputSchema={
                "type": "object",
                "required": ["session_id"],
                "properties": {"session_id": {"type": "string"}},
            },
        ),
        Tool(
            name="arcnet_model_intel",
            description="Model intelligence + recommendation buckets for an agent",
            inputSchema={
                "type": "object",
                "required": ["agent_id"],
                "properties": {"agent_id": {"type": "string"}},
            },
        ),
        Tool(
            name="arcnet_search_models",
            description="Search static model catalog (GET /api/models/catalog)",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {"type": "string"},
                    "status": {"type": "string"},
                    "capability_tier": {"type": "string"},
                    "min_context": {"type": "integer"},
                    "reasoning": {"type": "boolean"},
                },
            },
        ),
        Tool(
            name="arcnet_signals",
            description="Paginated signals for agent/session or fleet",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "session_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        Tool(
            name="arcnet_run_replay",
            description="Run Time Machine replay (requires confirm=true)",
            inputSchema={
                "type": "object",
                "required": ["session_id", "candidate_model", "confirm"],
                "properties": {
                    "session_id": {"type": "string"},
                    "candidate_model": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
            },
        ),
        Tool(
            name="arcnet_propose_model_change",
            description="Record model-change proposal note (requires confirm=true)",
            inputSchema={
                "type": "object",
                "required": ["agent_id", "to_model", "reason", "confirm"],
                "properties": {
                    "agent_id": {"type": "string"},
                    "to_model": {"type": "string"},
                    "reason": {"type": "string"},
                    "from_model": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    args = arguments or {}
    try:
        if name == "arcnet_fleet_health":
            payload = tools.fleet_health()
        elif name == "arcnet_search_threats":
            payload = tools.search_threats(
                agent_id=args.get("agent_id"),
                session_id=args.get("session_id"),
                limit=int(args.get("limit") or 50),
                offset=int(args.get("offset") or 0),
            )
        elif name == "arcnet_get_incident":
            payload = tools.get_incident(str(args["session_id"]))
        elif name == "arcnet_case_file":
            payload = tools.case_file(str(args["session_id"]))
        elif name == "arcnet_replay_verdicts":
            payload = tools.replay_verdicts(str(args["session_id"]))
        elif name == "arcnet_model_intel":
            payload = tools.model_intel(str(args["agent_id"]))
        elif name == "arcnet_search_models":
            payload = tools.search_models(
                provider=args.get("provider"),
                status=args.get("status"),
                capability_tier=args.get("capability_tier"),
                min_context=args.get("min_context"),
                reasoning=args.get("reasoning"),
            )
        elif name == "arcnet_signals":
            payload = tools.signals(
                agent_id=args.get("agent_id"),
                session_id=args.get("session_id"),
                limit=int(args.get("limit") or 50),
                offset=int(args.get("offset") or 0),
            )
        elif name == "arcnet_run_replay":
            payload = tools.run_replay(
                session_id=str(args["session_id"]),
                candidate_model=str(args["candidate_model"]),
                confirm=bool(args.get("confirm")),
            )
        elif name == "arcnet_propose_model_change":
            payload = tools.propose_model_change(
                agent_id=str(args["agent_id"]),
                to_model=str(args["to_model"]),
                reason=str(args["reason"]),
                confirm=bool(args.get("confirm")),
                from_model=args.get("from_model"),
            )
        else:
            payload = {"ok": False, "error": f"unknown tool {name}"}
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:500]}
    return [TextContent(type="text", text=tools.as_text(payload))]


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    os.environ.setdefault("ARCNET_SERVER_URL", "http://localhost:8000")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
