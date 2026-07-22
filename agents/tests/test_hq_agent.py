"""HQ Agent Agno definition — Unplug hooks + tool surface."""

from __future__ import annotations

import unittest


class HqAgentBuildTests(unittest.TestCase):
    def test_build_hq_agent_has_tools_and_guards(self) -> None:
        from hq_agent import HQ_TOOLS, build_hq_agent

        self.assertGreaterEqual(len(HQ_TOOLS), 10)
        agent = build_hq_agent(model="gpt-4o-mini")
        self.assertEqual(agent.id, "hq_agent")
        self.assertTrue(agent.pre_hooks)
        self.assertTrue(agent.post_hooks)
        self.assertTrue(agent.tool_hooks)


if __name__ == "__main__":
    unittest.main()
