"""AgentOS app hosting Agent J (+ fleet clones L & O)."""

from __future__ import annotations

import os

from agno.os import AgentOS
from dotenv import load_dotenv

from arcnet import init
from arcnet_agents.agent_j import build_agent_j, build_fleet_clone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(ROOT, ".env"))


def create_os() -> AgentOS:
    init(
        service_name="arcnet-agents",
        agent_id="agent_j",
        exposure="forward_facing",
        model=os.getenv("ARCNET_MODEL", "gpt-4o-mini"),
    )
    agent_j = build_agent_j()
    agent_l = build_fleet_clone(agent_id="agent_l", name="Agent L")
    agent_o = build_fleet_clone(agent_id="agent_o", name="Agent O")
    return AgentOS(
        id="arcnet-fleet",
        name="ArcNet Fleet",
        description="Demo AgentOS fleet for ArcNet",
        agents=[agent_j, agent_l, agent_o],
    )


agent_os = create_os()
app = agent_os.get_app()
