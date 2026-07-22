"""ArcNet SDK — instrumentation, guardrail, signals, replay, HQ reads, model explore."""

from __future__ import annotations

from arcnet.hq import check_session, incident_view, session_view, signals_view, sources_view
from arcnet.init import bind_session, init, shutdown
from arcnet.model_explore import (
    compare_replay_verdicts,
    fetch_provider_catalog,
    list_task_types,
    recommend_models,
    record_recommendation_note,
)
from arcnet.pricing import PRICES, cost_usd

__version__ = "0.1.0"
__all__ = [
    "PRICES",
    "bind_session",
    "check_session",
    "compare_replay_verdicts",
    "cost_usd",
    "fetch_provider_catalog",
    "incident_view",
    "init",
    "list_task_types",
    "recommend_models",
    "record_recommendation_note",
    "session_view",
    "shutdown",
    "signals_view",
    "sources_view",
    "__version__",
]
