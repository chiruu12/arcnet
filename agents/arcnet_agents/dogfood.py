"""Opt-in continuous work loop for fleet dogfood (``ARCNET_DOGFOOD=1``).

Runs genuine support/ops tasks against the real customer fixture DB — not
scripted Bug Suite scenarios. Off by default; separate entry point from AgentOS
and ``agents/scenarios/runner.py``.

Run::

    ARCNET_DOGFOOD=1 PYTHONPATH=sdk:server:. .venv/bin/python -m arcnet_agents.dogfood
"""

from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from opentelemetry import trace

from arcnet import bind_session, init, shutdown
from arcnet.context import get_runtime
from arcnet.guard_factory import build_guard
from arcnet.ids import new_id
from arcnet.pricing import cost_usd
from arcnet.transcript import persist_session, prompt_ref, start_session_row
from arcnet_agents.agent_j import PROMPT_J, build_agent_j, build_fleet_clone
from arcnet_agents.tools import load_customers

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

logger = logging.getLogger("arcnet.dogfood")

_STOP = False

FLEET = (
    {
        "agent_id": "agent_j",
        "name": "Agent J",
        "role": "support/ops",
        "exposure": "forward_facing",
    },
    {
        "agent_id": "agent_l",
        "name": "Agent L",
        "role": "fleet background",
        "exposure": "forward_facing",
    },
    {
        "agent_id": "agent_o",
        "name": "Agent O",
        "role": "fleet background",
        "exposure": "forward_facing",
    },
)


@dataclass(frozen=True)
class DogfoodConfig:
    interval_s: float
    max_iterations: int
    max_duration_s: float
    server_url: str
    model: str


@dataclass(frozen=True)
class DogfoodTask:
    agent_id: str
    agent_name: str
    role: str
    exposure: str
    goal: str
    kind: str


def dogfood_enabled() -> bool:
    return os.getenv("ARCNET_DOGFOOD", "").strip().lower() in ("1", "true", "yes")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def config_from_env() -> DogfoodConfig:
    return DogfoodConfig(
        interval_s=max(30.0, _env_float("ARCNET_DOGFOOD_INTERVAL_S", 300.0)),
        max_iterations=max(1, _env_int("ARCNET_DOGFOOD_MAX_ITERATIONS", 48)),
        max_duration_s=max(60.0, _env_float("ARCNET_DOGFOOD_MAX_DURATION_S", 86_400.0)),
        server_url=os.getenv("ARCNET_SERVER_URL", "http://localhost:8000").rstrip("/"),
        model=os.getenv("ARCNET_MODEL", "gpt-4o-mini"),
    )


def has_model_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _active_orders() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for customer in load_customers():
        for order in customer.get("orders") or []:
            rows.append(
                {
                    "order_id": str(order.get("order_id", "")),
                    "customer": str(customer.get("name", "")),
                    "status": str(order.get("status", "")),
                    "carrier": str(order.get("carrier") or ""),
                    "eta": str(order.get("eta") or ""),
                }
            )
    return rows


def pick_task(iteration: int) -> DogfoodTask:
    """Select a genuine ops task from the live customer fixture DB."""
    orders = _active_orders()
    if not orders:
        raise RuntimeError("customer fixture DB is empty — cannot pick dogfood task")

    fleet = FLEET[iteration % len(FLEET)]
    kind_idx = (iteration // len(FLEET)) % 3
    order = orders[iteration % len(orders)]

    if kind_idx == 0:
        goal = (
            f"Look up order #{order['order_id']} for customer {order['customer']} "
            f"and give a one-paragraph ops summary (status, carrier, ETA if any). "
            f"Do not include SSN or other sensitive fields."
        )
        kind = "order_status"
    elif kind_idx == 1:
        processing = [o for o in orders if o["status"] == "processing"]
        if processing:
            ids = ", ".join(f"#{o['order_id']}" for o in processing)
            goal = (
                f"Check which orders are still processing ({ids}) and recommend "
                f"whether any need escalation. Use lookup_customer only — do not send email."
            )
        else:
            goal = (
                "List every order in the customer store that is not delivered yet "
                "and summarize which need follow-up. Use lookup_customer and run_query only."
            )
        kind = "processing_triage"
    else:
        shipped = [o for o in orders if o["status"] == "shipped"]
        sample = shipped[iteration % len(shipped)] if shipped else order
        goal = (
            f"Confirm shipping status for order #{sample['order_id']} via lookup_customer "
            f"and run_query if helpful. Summarize for the daily standup — no SSN."
        )
        kind = "shipped_check"

    return DogfoodTask(
        agent_id=fleet["agent_id"],
        agent_name=fleet["name"],
        role=fleet["role"],
        exposure=fleet["exposure"],
        goal=goal,
        kind=kind,
    )


def _reset_session_guard(runtime: Any) -> None:
    runtime.taint_sources.clear()
    runtime.guard = build_guard()


def _usage_from_run(run: Any, model: str, latency_ms: float) -> dict[str, Any]:
    metrics = getattr(run, "metrics", None)
    inp = int(getattr(metrics, "input_tokens", 0) or 0) if metrics else 0
    out = int(getattr(metrics, "output_tokens", 0) or 0) if metrics else 0
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "cost_usd": cost_usd(model, inp, out),
        "latency_ms": latency_ms,
    }


def _trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        return format(ctx.trace_id, "032x")
    return None


def _build_agent_for_task(task: DogfoodTask, *, model: str) -> Any:
    if task.agent_id == "agent_j":
        return build_agent_j(
            agent_id=task.agent_id,
            name=task.agent_name,
            role=task.role,
            model=model,
        )
    return build_fleet_clone(
        agent_id=task.agent_id,
        name=task.agent_name,
        role=task.role,
        model=model,
    )


def run_dogfood_iteration(
    task: DogfoodTask,
    *,
    server_url: str,
    model: str,
) -> dict[str, Any]:
    """Run one instrumented dogfood task — same SDK path as scenario runner."""
    session_id = new_id("s_")
    bind_session(session_id)
    rt = get_runtime()
    _reset_session_guard(rt)
    rec = start_session_row(
        session_id=session_id,
        agent_id=task.agent_id,
        goal=task.goal,
        model=model,
        scenario="dogfood",
        system_prompt_ref=prompt_ref(PROMPT_J),
        temperature=0.0,
        server_url=server_url,
        exposure=task.exposure,
        agent_name=task.agent_name,
        role=task.role,
    )
    rt.transcript = rec
    agent = _build_agent_for_task(task, model=model)
    t0 = time.perf_counter()
    content = ""
    status = "completed"
    try:
        run = agent.run(task.goal)
        content = str(getattr(run, "content", "") or "")
        usage = _usage_from_run(run, model, (time.perf_counter() - t0) * 1000)
        rt.tokens_total.add(
            usage["input_tokens"] + usage["output_tokens"],
            {"agent_id": task.agent_id, "model": model},
        )
        rt.cost_usd.add(usage["cost_usd"], {"agent_id": task.agent_id, "model": model})
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        content = str(exc)
        usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }

    outcome = {
        "goal_reached": "clean" if content.strip() else "failed",
        "exfil_attempts": 0,
        "steps": len(rec.steps),
        "tool_errors": 0,
        "dogfood_kind": task.kind,
    }
    rec.finish(
        final_output=content,
        status=status,
        outcome=outcome,
        usage=usage,
        trace_id=_trace_id(),
    )
    persist_session(rec, server_url=server_url)
    return {
        "session_id": session_id,
        "agent_id": task.agent_id,
        "kind": task.kind,
        "status": status,
        "steps": len(rec.steps),
        "usage": usage,
    }


def _on_stop(signum: int, _frame: Any) -> None:
    global _STOP
    logger.info("dogfood loop received signal %s — shutting down", signum)
    _STOP = True


def _sleep_interruptible(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while not _STOP and time.monotonic() < deadline:
        time.sleep(min(1.0, deadline - time.monotonic()))


def maybe_run_dogfood_loop() -> dict[str, Any]:
    """Entry for tests and operators. No-op when ``ARCNET_DOGFOOD`` is unset."""
    if not dogfood_enabled():
        return {
            "ran": False,
            "reason": "ARCNET_DOGFOOD not enabled",
        }
    iterations = run_dogfood_loop()
    return {"ran": True, "iterations": iterations}


def run_dogfood_loop() -> int:
    """Long-running bounded work loop. Requires ``ARCNET_DOGFOOD=1``."""
    if not dogfood_enabled():
        logger.info("ARCNET_DOGFOOD not set — dogfood loop disabled (no-op)")
        return 0

    cfg = config_from_env()
    global _STOP
    _STOP = False
    signal.signal(signal.SIGTERM, _on_stop)
    signal.signal(signal.SIGINT, _on_stop)

    init(
        service_name="arcnet-dogfood",
        agent_id="agent_j",
        exposure="forward_facing",
        model=cfg.model,
        server_url=cfg.server_url,
    )

    started = time.monotonic()
    completed = 0
    iteration = 0

    logger.info(
        "dogfood loop starting interval=%ss max_iter=%s max_duration=%ss server=%s",
        cfg.interval_s,
        cfg.max_iterations,
        cfg.max_duration_s,
        cfg.server_url,
    )

    try:
        while not _STOP and iteration < cfg.max_iterations:
            if time.monotonic() - started > cfg.max_duration_s:
                logger.info("dogfood loop hit max duration (%ss)", cfg.max_duration_s)
                break

            if not has_model_key():
                logger.warning(
                    "OPENAI_API_KEY missing — dogfood idle (retry in %ss, no model calls)",
                    cfg.interval_s,
                )
                _sleep_interruptible(cfg.interval_s)
                iteration += 1
                continue

            task = pick_task(completed)
            try:
                result = run_dogfood_iteration(task, server_url=cfg.server_url, model=cfg.model)
                logger.info(
                    "dogfood iteration %s session=%s agent=%s kind=%s status=%s",
                    completed,
                    result.get("session_id"),
                    result.get("agent_id"),
                    result.get("kind"),
                    result.get("status"),
                )
                completed += 1
            except Exception:
                logger.exception("dogfood iteration %s failed", completed)

            iteration += 1
            if _STOP or iteration >= cfg.max_iterations:
                break
            _sleep_interruptible(cfg.interval_s)
    finally:
        shutdown()

    logger.info("dogfood loop stopped after %s completed task(s)", completed)
    return completed


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not dogfood_enabled():
        logger.info(
            "ARCNET_DOGFOOD is unset — nothing started. "
            "Set ARCNET_DOGFOOD=1 to enable the continuous work loop."
        )
        return 0
    run_dogfood_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
