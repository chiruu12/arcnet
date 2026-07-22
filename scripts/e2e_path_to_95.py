#!/usr/bin/env python3
"""WS9 e2e: seed → propose → apply(confirm) → pin → check version_pinpoint.

Uses a scratch SQLite DB + FastAPI TestClient (no live server required).
Exit 0 on success; non-zero with a clear message on failure.

  PYTHONPATH=sdk:server ARCNET_DB_PATH=/tmp/arcnet_e2e.db \\
    uv run python scripts/e2e_path_to_95.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fail(msg: str) -> int:
    print(f"e2e FAIL: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    sys.path.insert(0, str(ROOT / "sdk"))
    sys.path.insert(0, str(ROOT / "server"))

    with tempfile.TemporaryDirectory(prefix="arcnet_e2e_") as tmp_name:
        db_path = Path(tmp_name) / "e2e.db"
        os.environ["ARCNET_DB_PATH"] = str(db_path)
        # Avoid accidental live AgentOS probes during apply.
        os.environ.pop("ARCNET_AGENTOS_URL", None)

        from fastapi.testclient import TestClient

        import arcnet_server.main as m

        m._conn = None
        client = TestClient(m.app)
        try:
            return _run(client)
        finally:
            client.close()


def _run(client) -> int:
    # --- seed ---
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

    sid = f"s_e2e_{int(time.time())}"
    sess = client.post(
        "/api/sessions",
        json={
            "session_id": sid,
            "agent_id": "agent_j",
            "scenario": "S1",
            "goal": "e2e propose-apply-pin",
            "model": "gpt-4o-mini",
            "status": "completed",
        },
    )
    if sess.status_code != 200:
        return _fail(f"seed session: {sess.status_code} {sess.text}")

    # Baseline version so cascade/timeline is non-empty
    ver = client.post(
        "/api/agents/agent_j/versions",
        json={
            "version": "e2e.baseline",
            "model": "gpt-4o-mini",
            "source_ref": "scripts/e2e_path_to_95.py",
            "notes": "e2e baseline",
        },
    )
    if ver.status_code != 200:
        return _fail(f"seed version: {ver.status_code} {ver.text}")

    # --- propose ---
    prop = client.post(
        "/api/signal",
        json={
            "agent_id": "agent_j",
            "session_id": sid,
            "kind": "note",
            "severity": "info",
            "reason": "e2e: upgrade for injection_resist",
            "guidance": (
                "Proposed model change for agent_j: gpt-4o-mini → gpt-4o. "
                "evidence_refs=agent:agent_j,session:" + sid
            ),
            "source": "hq_agent",
        },
    )
    if prop.status_code != 200:
        return _fail(f"propose: {prop.status_code} {prop.text}")
    proposal = prop.json()
    proposal_id = proposal.get("signal_id")
    if not proposal_id:
        return _fail(f"propose missing signal_id: {proposal}")

    # --- apply(confirm) + pin session ---
    apply = client.post(
        "/api/agents/agent_j/apply-model",
        json={
            "confirm": True,
            "model": "gpt-4o",
            "version": "e2e.apply.1",
            "session_id": sid,
            "proposal_signal_id": proposal_id,
            "source_ref": "e2e:apply",
            "notes": "e2e apply with pin",
        },
    )
    if apply.status_code != 200:
        return _fail(f"apply: {apply.status_code} {apply.text}")
    applied = apply.json()
    if not applied.get("applied"):
        return _fail(f"apply not applied: {applied}")
    if not applied.get("agentos_reload_required"):
        return _fail(f"missing agentos_reload_required: {applied}")
    version_row = applied.get("version") or {}
    version_id = version_row.get("version_id")
    if not version_id:
        return _fail(f"apply missing version_id: {applied}")

    # --- pin verified on session row ---
    pinned = client.get(f"/api/sessions/{sid}")
    if pinned.status_code != 200:
        return _fail(f"get session: {pinned.status_code} {pinned.text}")
    if pinned.json().get("agent_version") != version_id:
        return _fail(
            f"session pin mismatch: got {pinned.json().get('agent_version')} "
            f"want {version_id}"
        )

    # --- check asserts version_pinpoint ---
    check = client.get(f"/api/agent-view/check/{sid}")
    if check.status_code != 200:
        return _fail(f"check: {check.status_code} {check.text}")
    body = check.json()
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    pin = (data or {}).get("version_pinpoint")
    if not isinstance(pin, dict):
        return _fail(f"check missing version_pinpoint: {body}")
    if pin.get("version_id") != version_id:
        return _fail(
            f"version_pinpoint.version_id={pin.get('version_id')} want {version_id}"
        )
    if not pin.get("pinned_session_matches"):
        return _fail(f"version_pinpoint.pinned_session_matches false: {pin}")
    if not (pin.get("narrative") or pin.get("version")):
        return _fail(f"version_pinpoint thin: {pin}")

    print("e2e OK: seed → propose → apply(confirm) → pin → version_pinpoint")
    print(f"  session={sid}")
    print(f"  version_id={version_id}")
    print(f"  agentos_reload_required={applied.get('agentos_reload_required')}")
    print(f"  pinpoint.version={pin.get('version')} model={pin.get('model')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
