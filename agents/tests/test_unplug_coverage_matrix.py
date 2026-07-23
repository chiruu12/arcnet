"""Programmatic WS8 coverage matrix checklist (P5-A).

Keeps docs/plans/unplug-coverage-matrix.md honest: every in-scope
agent × tool × checkpoint row must be COVERED or explicitly DEFER/N/A.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX_DOC = ROOT / "docs" / "plans" / "unplug-coverage-matrix.md"

FLEET_TOOLS = (
    "fetch_url",
    "lookup_customer",
    "get_customer_profile",
    "send_email",
    "run_query",
    "paginate_records",
)

HQ_TOOLS = (
    "signoz_status",
    "signoz_evidence",
    "fleet_overview",
    "agent_signals",
    "session_check",
    "case_file_view",
    "replay_compare",
    "griffin_anomalies",
    "list_agent_models",
    "recommend_models",
    "agent_version_timeline",
    "register_agent_version",
    "propose_model_change",
    "list_model_proposals",
)

CHECKPOINTS = ("input", "retrieved", "tool_call", "output")

IN_SCOPE_AGENTS: dict[str, tuple[str, ...]] = {
    "agent_j": FLEET_TOOLS,
    "agent_l": FLEET_TOOLS,
    "agent_o": FLEET_TOOLS,
    "hq_agent": HQ_TOOLS,
}


def _retrieved_applies(agent_id: str, tool: str) -> bool:
    return agent_id != "hq_agent" and tool == "fetch_url"


class UnplugCoverageMatrixTests(unittest.TestCase):
    def test_matrix_doc_exists(self) -> None:
        self.assertTrue(MATRIX_DOC.is_file(), f"missing {MATRIX_DOC}")

    def test_in_scope_agents_wired_with_four_hooks(self) -> None:
        from arcnet_agents.agent_j import build_agent_j, build_fleet_clone
        from hq_agent import HQ_TOOLS as HQ_AGENT_TOOLS, build_hq_agent

        agents = [
            build_agent_j(),
            build_fleet_clone(agent_id="agent_l", name="Agent L"),
            build_fleet_clone(agent_id="agent_o", name="Agent O"),
            build_hq_agent(model="gpt-4o-mini"),
        ]
        for agent in agents:
            self.assertTrue(agent.pre_hooks, f"{agent.id} missing pre_hooks")
            self.assertTrue(agent.post_hooks, f"{agent.id} missing post_hooks")
            self.assertTrue(agent.tool_hooks, f"{agent.id} missing tool_hooks")

        fleet_tool_names = {t.name for t in agents[0].tools or []}
        self.assertEqual(fleet_tool_names, set(FLEET_TOOLS))
        hq_tool_names = {t.name for t in agents[3].tools or []}
        self.assertEqual(hq_tool_names, set(HQ_TOOLS))
        self.assertEqual(len(HQ_AGENT_TOOLS), len(HQ_TOOLS))

    def test_matrix_table_has_row_per_agent_tool_checkpoint(self) -> None:
        text = MATRIX_DOC.read_text()
        missing: list[str] = []
        for agent_id, tools in IN_SCOPE_AGENTS.items():
            for tool in tools:
                for cp in CHECKPOINTS:
                    pattern = rf"\|\s*{re.escape(agent_id)}\s*\|\s*{re.escape(tool)}\s*\|\s*{re.escape(cp)}\s*\|"
                    if not re.search(pattern, text):
                        missing.append(f"{agent_id}/{tool}/{cp}")
        self.assertFalse(
            missing,
            f"matrix doc missing {len(missing)} rows (first 5): {missing[:5]}",
        )

    def test_matrix_no_silent_holes(self) -> None:
        """Every data row must have Status COVERED, N/A, or DEFER."""
        text = MATRIX_DOC.read_text()
        in_table = False
        bad: list[str] = []
        for line in text.splitlines():
            if line.startswith("| Agent |"):
                in_table = True
                continue
            if in_table and line.startswith("|") and not line.startswith("|---"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 4:
                    continue
                status = cells[3].upper()
                if status not in ("COVERED", "N/A", "DEFER"):
                    bad.append(line)
            if in_table and line.startswith("## Explicit DEFER"):
                break
        self.assertFalse(bad, f"rows without COVERED/N/A/DEFER: {bad[:3]}")

    def test_expected_na_retrieved_rows(self) -> None:
        text = MATRIX_DOC.read_text()
        for agent_id, tools in IN_SCOPE_AGENTS.items():
            for tool in tools:
                if _retrieved_applies(agent_id, tool):
                    continue
                pattern = (
                    rf"\|\s*{re.escape(agent_id)}\s*\|\s*{re.escape(tool)}\s*\|\s*retrieved\s*\|\s*N/A"
                )
                self.assertRegex(
                    text,
                    pattern,
                    msg=f"expected retrieved N/A for {agent_id}/{tool}",
                )

    def test_matrix_stats_documented(self) -> None:
        text = MATRIX_DOC.read_text()
        self.assertIn("COVERED", text)
        self.assertIn("DEFER", text)
        self.assertRegex(text, r"\|\s*\*\*Total rows\*\*\s*\|\s*\d+\s*\|")


if __name__ == "__main__":
    unittest.main()
