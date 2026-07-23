#!/usr/bin/env python3
"""P9-C integration proof — P8 surfaces compose into one offline product loop.

Scratch SQLite via ARCNET_DB_PATH + FastAPI TestClient (same pattern as
``scripts/e2e_path_to_95.py``). No OpenAI / replay.run / live scenarios.

  uv sync --all-packages --all-groups && uv pip install pytest
  .venv/bin/python scripts/e2e_product_coherence.py

Exit 0 with compact PASS per section; non-zero on any failure.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

ENVELOPE_KEYS = ("view", "id", "data", "links", "hints")


def _fail(msg: str) -> int:
    print(f"coherence FAIL: {msg}", file=sys.stderr)
    return 1


def _pass(label: str, detail: str = "") -> None:
    line = f"PASS {label}"
    if detail:
        line += f" — {detail}"
    print(line)


def _assert_envelope(body: dict[str, Any], *, ctx: str) -> None:
    for key in ENVELOPE_KEYS:
        if key not in body:
            raise AssertionError(f"{ctx}: missing envelope key {key!r}")


def _get(client, path: str, *, ctx: str) -> dict[str, Any]:
    res = client.get(path)
    if res.status_code != 200:
        raise AssertionError(f"{ctx}: GET {path} -> {res.status_code} {res.text}")
    body = res.json()
    if path.startswith("/api/agent-view/"):
        _assert_envelope(body, ctx=ctx)
    return body


def _loop_path(loop: list[dict[str, Any]], view: str, **subs: str) -> str:
    for item in loop:
        if item.get("view") == view:
            path = str(item["path"])
            for key, val in subs.items():
                path = path.replace(f"<{key}>", val)
            if "<" in path:
                raise AssertionError(f"loop path for {view} still has placeholders: {path}")
            return path
    raise AssertionError(f"loop missing view={view!r}")


def _run_seed_scripts(db_path: Path) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "seed_demo.py"),
            "--db",
            str(db_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_hero_rows(client) -> tuple[str, str]:
    """Agent J + session for verdict / proposal graph edges."""
    agent = client.post(
        "/api/agents",
        json={
            "agent_id": "agent_j",
            "name": "Agent J",
            "exposure": "forward_facing",
            "model": "gpt-4o-mini",
        },
    )
    if agent.status_code != 200:
        raise AssertionError(f"seed agent_j: {agent.status_code} {agent.text}")

    sid = f"s_p9c_{int(time.time())}"
    transcript = {
        "session_id": sid,
        "scenario": "S1",
        "goal": "p9c verdict roundtrip",
        "steps": [
            {
                "i": 0,
                "type": "tool_call",
                "tool": "fetch_url",
                "trust_level": "retrieved",
                "guard": {"checkpoint": "input", "action": "block", "rule": "ignore_previous"},
            },
            {"i": 1, "type": "model_turn", "output_digest": "blocked"},
        ],
    }
    sess = client.post(
        "/api/sessions",
        json={
            "session_id": sid,
            "agent_id": "agent_j",
            "scenario": "S1",
            "goal": "p9c verdict roundtrip",
            "model": "gpt-4o-mini",
            "status": "failed",
            "transcript": transcript,
        },
    )
    if sess.status_code != 200:
        raise AssertionError(f"seed session: {sess.status_code} {sess.text}")

    prop = client.post(
        "/api/signal",
        json={
            "agent_id": "agent_j",
            "session_id": sid,
            "kind": "note",
            "severity": "info",
            "reason": "p9c graph-walk proposal",
            "guidance": f"Proposed model change for agent_j: gpt-4o-mini → gpt-4o session:{sid}",
            "source": "hq_agent",
        },
    )
    if prop.status_code != 200:
        raise AssertionError(f"seed proposal: {prop.status_code} {prop.text}")

    return "agent_j", sid


def _section_seed_sanity(client) -> str:
    home = _get(client, "/api/agent-view/home/all", ctx="seed/home")
    stats = home["data"].get("stats") or {}
    if int(stats.get("agents") or 0) < 1:
        raise AssertionError(f"home stats.agents < 1: {stats}")

    fleet = _get(client, "/api/agent-view/fleet_health/all", ctx="seed/fleet")
    agents = fleet["data"].get("agents") or []
    if not agents:
        raise AssertionError("fleet_health agents empty after seed_demo")

    signals = _get(client, "/api/agent-view/signals/all", ctx="seed/signals")
    if signals["data"].get("scope") != "fleet":
        raise AssertionError(f"signals scope not fleet: {signals['data'].get('scope')}")

    return str(agents[0]["agent_id"])


def _section_graph_walk(client, *, hero_agent: str, hero_session: str) -> None:
    home = _get(client, "/api/agent-view/home/all", ctx="walk/home")
    loop = home["data"].get("loop") or []

    # Follow concrete loop paths (no hand-built URLs where loop provides them).
    for stage in ("observe", "defend"):
        item = next(x for x in loop if x.get("stage") == stage)
        _get(client, str(item["path"]), ctx=f"walk/loop-{stage}")

    fleet = _get(client, str(home["links"]["fleet_health"]), ctx="walk/fleet-link")
    if fleet["links"].get("threats"):
        _get(client, str(fleet["links"]["threats"]), ctx="walk/fleet-threats-link")

    agent_id = hero_agent
    hq_path = _loop_path(loop, "hq_agent", agent_id=agent_id)
    hq = _get(client, hq_path, ctx="walk/hq_agent")
    if hq["data"]["agent"]["agent_id"] != agent_id:
        raise AssertionError("hq_agent agent mismatch")

    session_id = hero_session
    proposals = hq["data"].get("proposals") or []
    if proposals and proposals[0].get("session_id"):
        session_id = str(proposals[0]["session_id"])

    tm_path = _loop_path(loop, "time_machine", session_id=session_id)
    tm = _get(client, tm_path, ctx="walk/time_machine")
    case_path = tm["links"].get("case_files")
    if not case_path:
        raise AssertionError("time_machine missing links.case_files")
    case = _get(client, str(case_path), ctx="walk/case_files-link")
    if case["view"] != "case_files" or case["id"] != session_id:
        raise AssertionError(f"case_files twin mismatch: {case.get('view')}/{case.get('id')}")

    # Follow hq_agent graph links that exist (no hand-built agent-view URLs).
    for key in ("models", "versions", "versions_timeline", "signals_agent", "threats_agent"):
        link = hq["links"].get(key)
        if link:
            _get(client, str(link), ctx=f"walk/hq-link-{key}")


def _section_model_intel(client, agent_id: str) -> None:
    from arcnet_server import model_catalog

    res = client.get(f"/api/agents/{agent_id}/model-intel")
    if res.status_code != 200:
        raise AssertionError(f"model-intel: {res.status_code} {res.text}")
    body = res.json()
    if body.get("catalog_version") != "2026-07":
        raise AssertionError(f"catalog_version: {body.get('catalog_version')}")
    candidates = body.get("candidates") or []
    if not candidates:
        raise AssertionError("model-intel candidates empty")

    ue = body["usage_evidence"]
    inp = int(ue["input_tokens"])
    out = int(ue["output_tokens"])
    baseline = body.get("baseline_projected_cost_usd")
    expected_base = model_catalog.project_cost_usd(
        body.get("current_model"), input_tokens=inp, output_tokens=out
    )
    if expected_base is None or abs(float(baseline) - float(expected_base)) > 1e-8:
        raise AssertionError(f"baseline cost mismatch: {baseline} vs {expected_base}")

    pick = next((c for c in candidates if c["id"] == "o4-mini"), candidates[0])
    hand = model_catalog.project_cost_usd(
        pick["id"], input_tokens=inp, output_tokens=out
    )
    if hand is None:
        raise AssertionError(f"hand cost None for {pick['id']}")
    if abs(float(pick["projected_cost_usd"]) - float(hand)) > 1e-8:
        raise AssertionError(
            f"candidate {pick['id']} cost {pick['projected_cost_usd']} != hand {hand}"
        )

    apply = client.post(
        f"/api/agents/{agent_id}/apply-model",
        json={
            "confirm": True,
            "model": pick["id"],
            "version": "p9c.coherence.apply",
            "source_ref": "scripts/e2e_product_coherence.py",
            "notes": "p9c model-intel apply",
        },
    )
    if apply.status_code != 200:
        raise AssertionError(f"apply-model: {apply.status_code} {apply.text}")
    applied = apply.json()
    if not applied.get("applied"):
        raise AssertionError(f"apply not applied: {applied}")
    if "agentos_reload_required" not in applied:
        raise AssertionError("apply missing agentos_reload_required")

    timeline = client.get(f"/api/agents/{agent_id}/versions/timeline")
    if timeline.status_code != 200:
        raise AssertionError(f"timeline: {timeline.status_code}")
    tl = timeline.json()
    if tl.get("current_model") != pick["id"]:
        raise AssertionError(f"timeline current_model {tl.get('current_model')} != {pick['id']}")


def _section_verdict_roundtrip(client, *, agent_id: str, session_id: str) -> None:
    threat_id = f"thr_p9c_{int(time.time())}"
    payload = {
        "threat_id": threat_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "checkpoint": "input",
        "action": "block",
        "category": "injection",
        "subcategory": "ignore_previous",
        "pattern_class": "regex",
        "risk_score": 0.85,
        "evidence": "Matched pattern: ignore_previous",
        "findings_detail": [
            {
                "category": "injection",
                "subcategory": "ignore_previous",
                "stage": "regex",
                "score": 0.85,
                "evidence": "Matched pattern: ignore_previous",
            }
        ],
        "guard_verdict": {
            "checkpoint": "input",
            "action": "block",
            "rule": "ignore_previous",
            "pattern_class": "regex",
            "risk_score": 0.85,
        },
    }
    posted = client.post("/api/threats", json=payload)
    if posted.status_code != 200:
        raise AssertionError(f"POST threats: {posted.status_code} {posted.text}")
    row = posted.json()
    if row.get("pattern_class") != "regex":
        raise AssertionError(f"threat pattern_class missing: {row}")

    threats_env = _get(
        client, f"/api/agent-view/threats/{session_id}", ctx="verdict/threats-twin"
    )
    twin_rows = threats_env["data"].get("threats") or []
    hit = next((t for t in twin_rows if t.get("threat_id") == threat_id), None)
    if hit is None:
        raise AssertionError("agent-view threats missing posted row")
    if hit.get("subcategory") != "ignore_previous":
        raise AssertionError(f"agent-view threat subcategory: {hit.get('subcategory')}")
    if hit.get("checkpoint") != "input" or hit.get("action") != "block":
        raise AssertionError(f"agent-view threat shape thin: {hit}")

    raw = client.get("/api/threats").json()
    raw_hit = next(t for t in raw if t["threat_id"] == threat_id)
    if raw_hit["guard_verdict"]["rule"] != "ignore_previous":
        raise AssertionError("raw threats guard_verdict.rule missing")

    export = client.get(f"/export/case-file/{session_id}")
    if export.status_code != 200:
        raise AssertionError(f"export: {export.status_code}")
    with zipfile.ZipFile(io.BytesIO(export.content)) as zf:
        env = json.loads(zf.read("case-file.json"))
        md = zf.read("case-file.md").decode("utf-8")

    rc = (env.get("data") or {}).get("root_cause") or {}
    if rc.get("rule") != "ignore_previous":
        raise AssertionError(f"export root_cause.rule: {rc.get('rule')}")
    if rc.get("pattern_class") != "regex":
        raise AssertionError(f"export root_cause.pattern_class: {rc.get('pattern_class')}")
    if "rule=`ignore_previous`" not in md:
        raise AssertionError("export timeline missing guard rule line")


def _section_hitl(client) -> None:
    from arcnet_server.bus import BUS

    async def _next_hitl(timeout: float = 2.0) -> Any:
        return await asyncio.wait_for(q.get(), timeout=timeout)

    q = BUS.subscribe()
    try:
        created = client.post(
            "/api/hitl",
            json={
                "run_id": "run_p9c",
                "session_id": "s_p9c_hitl",
                "payload": {"reason": "p9c coherence", "tool": "send_email"},
            },
        )
        if created.status_code != 200:
            raise AssertionError(f"POST hitl: {created.status_code} {created.text}")
        body = created.json()
        hitl_id = body["hitl_id"]
        if body.get("status") != "pending":
            raise AssertionError(f"hitl not pending: {body}")

        loop = asyncio.new_event_loop()
        try:
            ev = loop.run_until_complete(_next_hitl())
        finally:
            loop.close()
        if ev.event != "hitl_request" or ev.data.get("hitl_id") != hitl_id:
            raise AssertionError(f"BUS publish miss: {ev}")

        listed = client.get("/api/hitl?status=pending")
        if listed.status_code != 200:
            raise AssertionError(f"GET hitl: {listed.status_code}")
        rows = listed.json()
        if not any(r["hitl_id"] == hitl_id for r in rows):
            raise AssertionError("pending list missing new hitl row")

        decided = client.post(f"/api/hitl/{hitl_id}", json={"decision": "approved"})
        if decided.status_code != 200:
            raise AssertionError(f"decide: {decided.status_code} {decided.text}")
        if decided.json().get("status") != "approved":
            raise AssertionError("decide status not approved")

        loop = asyncio.new_event_loop()
        try:
            ev2 = loop.run_until_complete(_next_hitl())
        finally:
            loop.close()
        if ev2.event != "hitl_request" or ev2.data.get("status") != "approved":
            raise AssertionError(f"BUS decide publish miss: {ev2}")

        pending = client.get("/api/hitl?status=pending").json()
        if any(r["hitl_id"] == hitl_id for r in pending):
            raise AssertionError("decided row still pending")
    finally:
        BUS.unsubscribe(q)


def main() -> int:
    sys.path.insert(0, str(ROOT / "sdk"))
    sys.path.insert(0, str(ROOT / "server"))

    with tempfile.TemporaryDirectory(prefix="arcnet_p9c_") as tmp_name:
        db_path = Path(tmp_name) / "coherence.db"
        os.environ["ARCNET_DB_PATH"] = str(db_path)
        os.environ.pop("ARCNET_AGENTOS_URL", None)

        from fastapi.testclient import TestClient

        import arcnet_server.main as m

        m._conn = None
        _run_seed_scripts(db_path)

        client = TestClient(m.app)
        try:
            hero_agent, hero_session = _seed_hero_rows(client)
            fleet_agent = _section_seed_sanity(client)
            _pass("SEED SANITY", f"agents={fleet_agent} hero={hero_agent}")

            _section_graph_walk(client, hero_agent=hero_agent, hero_session=hero_session)
            _pass("GRAPH WALK", f"home→fleet→hq_agent→case_files ({hero_session})")

            mi_agent = fleet_agent if fleet_agent != hero_agent else "agent_l"
            _section_model_intel(client, mi_agent)
            _pass("MODEL-INTEL LOOP", f"agent={mi_agent} catalog apply + timeline")

            _section_verdict_roundtrip(
                client, agent_id=hero_agent, session_id=hero_session
            )
            _pass("VERDICT ROUNDTRIP", f"threats twin + export ({hero_session})")

            _section_hitl(client)
            _pass("HITL LOOP", "create→list→decide + BUS hitl_request")

        except AssertionError as exc:
            return _fail(str(exc))
        finally:
            client.close()

    print()
    print("coherence OK — P9-C integration proof (offline)")
    print("  live replay DEFER to driver session (quota-gated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
