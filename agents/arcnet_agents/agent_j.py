"""Agent J factory — support/ops, forward_facing, four tools + Unplug hooks."""

from __future__ import annotations

import os
from pathlib import Path

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from arcnet.guardrail import build_guard_hooks
from arcnet_agents.tools import TOOLS

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
PROMPT_J = PROMPTS / "j.md"


def build_agent_j(
    *,
    agent_id: str = "agent_j",
    name: str = "Agent J",
    model: str | None = None,
    temperature: float = 0.0,
) -> Agent:
    model_id = model or os.getenv("ARCNET_MODEL", "gpt-4o-mini")
    hooks = build_guard_hooks()
    return Agent(
        id=agent_id,
        name=name,
        model=OpenAIChat(id=model_id, temperature=temperature),
        tools=list(TOOLS),
        instructions=PROMPT_J.read_text(),
        pre_hooks=[hooks["input_guardrail"]],
        post_hooks=[hooks["output_post_hook"]],
        tool_hooks=[hooks["tool_call_middleware"]],
        session_state={},
        markdown=False,
    )


def build_fleet_clone(
    *,
    agent_id: str,
    name: str,
    role: str = "fleet background",
    model: str | None = None,
) -> Agent:
    """Agents L & O — clones of J with distinct ids (docs/11)."""
    _ = role
    return build_agent_j(agent_id=agent_id, name=name, model=model)
