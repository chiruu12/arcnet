"""Keep the server suite hermetic: no outbound HITL relay unless a test opts in.

``hitl_relay`` defaults to the local AgentOS (same default as ``replay_service``),
so an unset environment would make the suite issue real HTTP to :7777 — slow when
nothing is listening, and state-changing when something is. Tests that exercise
the relay set ``ARCNET_AGENTOS_URL`` themselves via ``patch.dict``.
"""

from __future__ import annotations

import os

os.environ["ARCNET_AGENTOS_URL"] = ""
