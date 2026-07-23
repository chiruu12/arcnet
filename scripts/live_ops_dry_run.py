#!/usr/bin/env python3
"""Phase 4 live-ops dry-run — propose→apply→pin + pagination + session filters.

Uses scratch SQLite + FastAPI TestClient (no live :8000 required). When
``ARCNET_AGENTOS_URL`` is set, probes ``/internal/runtime`` for reload honesty;
otherwise records probe-skipped (still asserts agentos_reload_required).

Exit 0 on success. Checklist printed for operators.

  PYTHONPATH=sdk:server uv run python scripts/live_ops_dry_run.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _fail(msg: str) -> int:
    print(f"live_ops FAIL: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    sys.path.insert(0, str(ROOT / "sdk"))
    sys.path.insert(0, str(ROOT / "server"))

    with tempfile.TemporaryDirectory(prefix="arcnet_live_ops_") as tmp_name:
        db_path = Path(tmp_name) / "live_ops.db"
        os.environ["ARCNET_DB_PATH"] = str(db_path)
        # Default: no live AgentOS — probe path covered via mocked URL in tests.
        agentos = (os.getenv("ARCNET_AGENTOS_URL") or "").strip()

        from fastapi.testclient import TestClient

        import arcnet_server.main as m

        m._conn = None
        client = TestClient(m.app)
        try:
            return _run(client, agentos_url=agentos)
        finally:
            client.close()


def _run(client, *, agentos_url: str) -> int:
    print("=== Phase 4 live-ops dry-run checklist ===")
    print("1. seed agent + session + oversized signal list")
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
        return _fail(f"seed agent: {agent.status_code} {agent.text}")

    sid = f"s_live_{int(time.time())}"
    sess = client.post(
        "/api/sessions",
        json={
            "session_id": sid,
            "agent_id": "agent_j",
            "scenario": "S1",
            "goal": "live ops dry-run",
            "model": "gpt-4o-mini",
            "status": "completed",
        },
    )
    if sess.status_code != 200:
        return _fail(f"seed session: {sess.status_code} {sess.text}")

    # Oversized list so X-Total-Count > page size (HQ "showing N of Total").
    for i in range(55):
        r = client.post(
            "/api/signal",
            json={
                "agent_id": "agent_j",
                "session_id": sid if i % 5 == 0 else None,
                "kind": "note",
                "severity": "info",
                "reason": f"live_ops filler {i}",
                "source": "ops",
            },
        )
        if r.status_code != 200:
            return _fail(f"seed signal {i}: {r.status_code}")

    print("2. propose → apply(confirm) → pin")
    prop = client.post(
        "/api/signal",
        json={
            "agent_id": "agent_j",
            "session_id": sid,
            "kind": "note",
            "severity": "info",
            "reason": "live_ops: upgrade for injection_resist",
            "guidance": (
                "Proposed model change for agent_j: gpt-4o-mini → gpt-4o. "
                f"evidence_refs=agent:agent_j,session:{sid}"
            ),
            "source": "hq_agent",
        },
    )
    if prop.status_code != 200:
        return _fail(f"propose: {prop.status_code} {prop.text}")
    proposal_id = prop.json().get("signal_id")
    if not proposal_id:
        return _fail(f"propose missing signal_id: {prop.json()}")

    apply_body = {
        "confirm": True,
        "model": "gpt-4o",
        "version": "live_ops.apply.1",
        "session_id": sid,
        "proposal_signal_id": proposal_id,
        "source_ref": "scripts/live_ops_dry_run.py",
        "notes": "live ops apply with pin",
    }

    if agentos_url:
        apply = client.post("/api/agents/agent_j/apply-model", json=apply_body)
    else:
        # Deterministic probe path without live AgentOS: pretend URL set + unreachable.
        with patch.dict(os.environ, {"ARCNET_AGENTOS_URL": "http://127.0.0.1:9"}, clear=False):
            apply = client.post("/api/agents/agent_j/apply-model", json=apply_body)

    if apply.status_code != 200:
        return _fail(f"apply: {apply.status_code} {apply.text}")
    applied = apply.json()
    if not applied.get("applied"):
        return _fail(f"apply not applied: {applied}")
    if "agentos_reload_required" not in applied:
        return _fail(f"missing agentos_reload_required: {applied}")
    probe = applied.get("agentos_probe") or {}
    if not isinstance(probe, dict) or "note" not in probe:
        return _fail(f"missing agentos_probe: {applied}")
    if probe.get("models_match") is True and applied.get("agentos_reload_required") is not False:
        return _fail(f"models_match but reload_required still true: {applied}")
    if probe.get("models_match") is not True and not applied.get("agentos_reload_required"):
        return _fail(f"expected agentos_reload_required when models differ: {applied}")
    version_row = applied.get("version") or {}
    version_id = version_row.get("version_id")
    if not version_id:
        return _fail(f"apply missing version_id: {applied}")

    print("3. session pin + version_pinpoint")
    pinned = client.get(f"/api/sessions/{sid}")
    if pinned.status_code != 200:
        return _fail(f"get session: {pinned.status_code}")
    if pinned.json().get("agent_version") != version_id:
        return _fail(
            f"session pin mismatch: got {pinned.json().get('agent_version')} want {version_id}"
        )
    check = client.get(f"/api/agent-view/check/{sid}")
    if check.status_code != 200:
        return _fail(f"check: {check.status_code}")
    body = check.json()
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    pin = (data or {}).get("version_pinpoint")
    if not isinstance(pin, dict) or pin.get("version_id") != version_id:
        return _fail(f"version_pinpoint bad: {pin}")

    print("4. session filters agent_version / version_id")
    by_av = client.get(
        f"/api/sessions?agent_id=agent_j&agent_version={version_id}&limit=10"
    )
    by_vid = client.get(
        f"/api/sessions?agent_id=agent_j&version_id={version_id}&limit=10"
    )
    if by_av.status_code != 200 or by_vid.status_code != 200:
        return _fail("session filter request failed")
    if by_av.headers.get("X-Total-Count") != by_vid.headers.get("X-Total-Count"):
        return _fail("agent_version vs version_id totals diverge")
    if int(by_av.headers.get("X-Total-Count", "0")) < 1:
        return _fail("filtered sessions total < 1")
    if not any(r.get("session_id") == sid for r in by_av.json()):
        return _fail("pinned session missing from agent_version filter")

    print("5. pagination totals under list sizes")
    page = client.get("/api/signals?agent_id=agent_j&limit=40&offset=0")
    if page.status_code != 200:
        return _fail(f"signals page: {page.status_code}")
    total = int(page.headers.get("X-Total-Count", "0"))
    if total <= 40:
        return _fail(f"expected X-Total-Count > 40, got {total}")
    if len(page.json()) != 40:
        return _fail(f"expected page len 40, got {len(page.json())}")
    proposals = client.get(
        "/api/signals?agent_id=agent_j&source=hq_agent&limit=40&offset=0"
    )
    if int(proposals.headers.get("X-Total-Count", "0")) < 1:
        return _fail("hq_agent proposals total < 1")

    print("6. AgentOS reload honesty")
    print(f"   agentos_reload_required={applied.get('agentos_reload_required')}")
    print(f"   agentos_probe.reachable={probe.get('reachable')}")
    print(f"   agentos_probe.models_match={probe.get('models_match')}")
    print(f"   agentos_probe.note={probe.get('note')}")
    if agentos_url and probe.get("reachable") and probe.get("models_match") is True:
        print("   OK: live AgentOS model already matches SQLite (restart not needed)")
    else:
        print(
            "   OK: reload required until operator restarts AgentOS "
            "(set ARCNET_MODEL=gpt-4o and reload :7777)"
        )

    print()
    print("live_ops OK: propose→apply→pin + filters + pagination + reload flag")
    print(f"  session={sid}")
    print(f"  version_id={version_id}")
    print(f"  signals_total={total} (page=40)")
    print()
    print("Operator follow-up (optional screenshots):")
    print("  - HQ #signals shows 'showing 40 of N' when N>40")
    print("  - HQ #hq_agent apply banner shows agentos_reload_required")
    print("  - After AgentOS restart with ARCNET_MODEL=gpt-4o, probe models_match=true")
    print("  - Case Files version filter shows session totals under agent_version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
