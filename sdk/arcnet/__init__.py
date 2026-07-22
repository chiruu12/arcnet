"""ArcNet SDK — instrumentation, guardrail, signals, replay, HQ reads, model explore."""

from __future__ import annotations

from arcnet.hq import check_session, incident_view, session_view, signals_view, sources_view
from arcnet.hq_tools import (
    agent_signals,
    agent_version_timeline,
    fleet_overview,
    griffin_anomalies,
    list_agent_models,
    list_model_proposals,
    propose_model_change,
    recommend_models as hq_recommend_models,
    register_agent_version,
    session_check,
    signoz_status,
)
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
    "agent_signals",
    "agent_version_timeline",
    "bind_session",
    "check_session",
    "compare_replay_verdicts",
    "cost_usd",
    "fetch_provider_catalog",
    "fleet_overview",
    "griffin_anomalies",
    "hq_recommend_models",
    "incident_view",
    "init",
    "list_agent_models",
    "list_model_proposals",
    "list_task_types",
    "propose_model_change",
    "recommend_models",
    "record_recommendation_note",
    "register_agent_version",
    "session_check",
    "session_view",
    "shutdown",
    "signals_view",
    "signoz_status",
    "sources_view",
    "__version__",
]
