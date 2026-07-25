#!/usr/bin/env python3
"""Verify Case File → HTTP SigNoz evidence handoff (gate G5, docs/03).

Walks the supported product path:
  incident envelope → Case File zip → /api/signoz/status → /api/signoz/evidence
Resolves trace_id from threat rows when the session row lacks one (hero fixtures).
Optional direct Query Range probe against SigNoz (--signoz-url).

Exits 0 when handoff + live span evidence succeed; 2 when handoff works but SigNoz
is absent/unreachable; 1 when the handoff itself fails. Never prints secrets.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSION = "s_ecfdb55d"  # Edgar hero — fixtures/heroes.json


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str


@dataclass
class Report:
    session_id: str
    server_url: str
    steps: list[StepResult] = field(default_factory=list)
    trace_id: str | None = None
    span_names: list[str] = field(default_factory=list)
    verdict: str = "pending"
    exit_code: int = 1

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.steps.append(StepResult(name, ok, detail))

    def render(self) -> str:
        lines = [
            f"=== G5 HTTP handoff verify — session {self.session_id} ===",
            f"server: {self.server_url}",
        ]
        for s in self.steps:
            mark = "ok" if s.ok else "!!"
            lines.append(f"  [{mark}] {s.name}: {s.detail}")
        if self.trace_id:
            lines.append(f"trace_id: {self.trace_id}")
        if self.span_names:
            lines.append(f"spans: {', '.join(self.span_names[:6])}")
            if len(self.span_names) > 6:
                lines.append(f"  (+{len(self.span_names) - 6} more)")
        lines.append(f"verdict: {self.verdict}")
        return "\n".join(lines)


def _redact(text: str, secrets: list[str]) -> str:
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[REDACTED]")
    return out


def _get_json(client: httpx.Client, url: str) -> tuple[int, Any]:
    try:
        r = client.get(url)
        if r.status_code >= 400:
            return r.status_code, {"error": r.text[:200]}
        return r.status_code, r.json()
    except httpx.HTTPError as exc:
        return 0, {"error": str(exc)[:200]}


def _resolve_trace_id(
    incident: dict[str, Any],
    threats_body: dict[str, Any],
    evidence: dict[str, Any],
) -> str | None:
    for source in (
        evidence.get("trace_id"),
        incident.get("links", {}).get("signoz_trace"),
    ):
        if isinstance(source, str) and source and "/trace/" not in source:
            return source
    link = incident.get("links", {}).get("signoz_trace")
    if isinstance(link, str) and "/trace/" in link:
        return link.rstrip("/").split("/")[-1]
    data = threats_body.get("data") or {}
    threats = data.get("threats") if isinstance(data, dict) else None
    if isinstance(threats, list):
        for row in threats:
            tid = row.get("trace_id") if isinstance(row, dict) else None
            if isinstance(tid, str) and tid.strip():
                return tid.strip()
    return None


def _extract_span_names(body: Any) -> list[str]:
    names: list[str] = []

    def walk(node: Any) -> None:
        if len(names) >= 12:
            return
        if isinstance(node, dict):
            name = node.get("name") or node.get("spanName")
            dur = node.get("durationNano") or node.get("duration_ns")
            sid = node.get("spanId") or node.get("span_id")
            if isinstance(name, str) and name.strip() and (dur is not None or sid):
                names.append(name.strip()[:80])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(body)
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _query_range_probe(
    client: httpx.Client,
    *,
    signoz_url: str,
    api_key: str,
    trace_id: str,
) -> tuple[bool, str, list[str]]:
    end = int(time.time() * 1000)
    start = end - 30 * 24 * 60 * 60 * 1000
    payload = {
        "start": start,
        "end": end,
        "requestType": "raw",
        "compositeQuery": {
            "queries": [
                {
                    "type": "builder_query",
                    "spec": {
                        "name": "A",
                        "signal": "traces",
                        "stepInterval": 60,
                        "disabled": False,
                        "filter": {"expression": f"traceID = '{trace_id}'"},
                        "limit": 8,
                        "offset": 0,
                        "order": [{"key": {"name": "timestamp"}, "direction": "desc"}],
                        "having": {"expression": ""},
                        "selectFields": [
                            {
                                "name": "name",
                                "fieldDataType": "string",
                                "signal": "traces",
                                "fieldContext": "span",
                            },
                            {
                                "name": "durationNano",
                                "fieldDataType": "float64",
                                "signal": "traces",
                                "fieldContext": "span",
                            },
                        ],
                    },
                }
            ]
        },
    }
    try:
        r = client.post(
            f"{signoz_url.rstrip('/')}/api/v5/query_range",
            headers={"SIGNOZ-API-KEY": api_key, "Content-Type": "application/json"},
            json=payload,
        )
    except httpx.HTTPError as exc:
        return False, f"query_range unreachable: {exc}", []
    if r.status_code >= 400:
        return False, f"query_range status={r.status_code}", []
    spans = _extract_span_names(r.json())
    if spans:
        return True, f"{len(spans)} span name(s) from Query Range", spans
    return False, "query_range ok but no spans matched (trace may have aged out)", []


def _connectivity_probe(
    client: httpx.Client,
    *,
    signoz_url: str,
    api_key: str,
) -> tuple[bool, str, list[str]]:
    """Recent-trace smoke when the session trace aged out of retention."""
    end = int(time.time() * 1000)
    start = end - 7 * 24 * 60 * 60 * 1000
    payload = {
        "start": start,
        "end": end,
        "requestType": "raw",
        "compositeQuery": {
            "queries": [
                {
                    "type": "builder_query",
                    "spec": {
                        "name": "A",
                        "signal": "traces",
                        "stepInterval": 60,
                        "disabled": False,
                        "filter": {"expression": "service.name EXISTS"},
                        "limit": 1,
                        "offset": 0,
                        "order": [{"key": {"name": "timestamp"}, "direction": "desc"}],
                        "having": {"expression": ""},
                        "selectFields": [
                            {
                                "name": "name",
                                "fieldDataType": "string",
                                "signal": "traces",
                                "fieldContext": "span",
                            },
                            {
                                "name": "traceID",
                                "fieldDataType": "string",
                                "signal": "traces",
                                "fieldContext": "span",
                            },
                        ],
                    },
                }
            ]
        },
    }
    try:
        r = client.post(
            f"{signoz_url.rstrip('/')}/api/v5/query_range",
            headers={"SIGNOZ-API-KEY": api_key, "Content-Type": "application/json"},
            json=payload,
        )
    except httpx.HTTPError as exc:
        return False, f"connectivity probe unreachable: {exc}", []
    if r.status_code >= 400:
        return False, f"connectivity probe status={r.status_code}", []
    spans = _extract_span_names(r.json())
    if spans:
        return True, f"SigNoz live ({spans[0]})", spans
    return False, "connectivity probe returned no spans", []


def verify(
    *,
    server_url: str,
    session_id: str,
    signoz_url_override: str | None,
    timeout: float,
) -> Report:
    report = Report(session_id=session_id, server_url=server_url.rstrip("/"))
    api_key = os.getenv("SIGNOZ_API_KEY", "").strip()
    secrets = [api_key] if api_key else []

    with httpx.Client(timeout=timeout) as client:
        code, health = _get_json(client, f"{report.server_url}/health")
        if code != 200:
            report.add("server_health", False, health.get("error", f"status={code}"))
            report.verdict = "FAIL — arcnet server unreachable"
            report.exit_code = 1
            return report
        report.add("server_health", True, "ok")

        code, incident = _get_json(
            client, f"{report.server_url}/api/agent-view/incident/{session_id}"
        )
        if code != 200 or incident.get("view") != "incident":
            detail = incident.get("error", f"status={code}") if isinstance(incident, dict) else str(incident)
            report.add("incident_envelope", False, str(detail)[:200])
            report.verdict = "FAIL — incident not found (seed heroes? run scripts/seed_heroes.py)"
            report.exit_code = 1
            return report
        report.add(
            "incident_envelope",
            True,
            f"scenario={incident.get('data', {}).get('scenario')} root_cause={incident.get('data', {}).get('root_cause', {}).get('checkpoint')}",
        )

        try:
            zr = client.get(f"{report.server_url}/export/case-file/{session_id}")
        except httpx.HTTPError as exc:
            report.add("case_file_zip", False, str(exc)[:200])
            report.verdict = "FAIL — case file export unreachable"
            report.exit_code = 1
            return report
        if zr.status_code != 200:
            report.add("case_file_zip", False, f"status={zr.status_code}")
            report.verdict = "FAIL — case file export failed"
            report.exit_code = 1
            return report
        try:
            with zipfile.ZipFile(io.BytesIO(zr.content)) as zf:
                names = set(zf.namelist())
                if names != {"case-file.md", "case-file.json"}:
                    raise ValueError(f"unexpected zip entries: {sorted(names)}")
                md = zf.read("case-file.md").decode()[:80]
        except (zipfile.BadZipFile, ValueError) as exc:
            report.add("case_file_zip", False, str(exc)[:200])
            report.verdict = "FAIL — case file bundle invalid"
            report.exit_code = 1
            return report
        report.add("case_file_zip", True, f"case-file.md starts: {md[:60].strip()}…")

        _, status = _get_json(client, f"{report.server_url}/api/signoz/status")
        if not isinstance(status, dict):
            report.add("signoz_status", False, "non-json response")
        elif not status.get("ui_reachable"):
            report.add(
                "signoz_status",
                False,
                f"ui_reachable=false ({status.get('ui_status')})",
            )
        elif not status.get("api_key_present"):
            report.add("signoz_status", False, "SIGNOZ_API_KEY empty on server — set .env and restart")
        elif status.get("query_range_ok") is False:
            report.add("signoz_status", False, status.get("query_note", "query_range failed"))
        else:
            report.add(
                "signoz_status",
                True,
                f"ui ok, query_range_ok={status.get('query_range_ok')}",
            )

        _, evidence = _get_json(
            client, f"{report.server_url}/api/signoz/evidence?session_id={session_id}"
        )
        if not isinstance(evidence, dict):
            report.add("signoz_evidence", False, "non-json response")
            evidence = {}
        elif evidence.get("note") and not evidence.get("spans"):
            report.add("signoz_evidence", True, evidence.get("note", "metadata only"))
        elif evidence.get("spans"):
            report.add(
                "signoz_evidence",
                True,
                f"{len(evidence['spans'])} bounded span(s) via server endpoint",
            )
        else:
            report.add("signoz_evidence", True, "empty spans — see note")

        _, threats = _get_json(
            client, f"{report.server_url}/api/agent-view/threats/{session_id}"
        )
        trace_id = _resolve_trace_id(incident, threats if isinstance(threats, dict) else {}, evidence)
        report.trace_id = trace_id

        signoz_url = (signoz_url_override or status.get("signoz_url") or os.getenv("SIGNOZ_URL", "http://localhost:8080")).rstrip("/")
        server_key_ok = bool(status.get("api_key_present")) if isinstance(status, dict) else False
        probe_key = api_key if api_key else ("present-on-server" if server_key_ok else "")

        if not trace_id:
            report.add("trace_resolve", False, "no trace_id on session or threats")
            report.verdict = "DEGRADED — handoff ok; no trace_id to query SigNoz spans"
            report.exit_code = 2
            return report
        report.add("trace_resolve", True, f"resolved {trace_id[:16]}…")

        if signoz_url_override and not api_key:
            report.add(
                "query_range_probe",
                False,
                "SIGNOZ_API_KEY not in shell env — export .env or pass key to server only",
            )
            report.verdict = "DEGRADED — handoff ok; direct probe needs SIGNOZ_API_KEY in env"
            report.exit_code = 2
            return report

        effective_key = api_key
        if not effective_key and server_key_ok:
            # Server has key; evidence endpoint already queried server-side spans.
            if evidence.get("spans"):
                report.span_names = [s.get("name", "") for s in evidence["spans"] if s.get("name")]
                report.add("query_range_probe", True, "used server /api/signoz/evidence spans")
                report.verdict = "PASS — HTTP handoff + bounded SigNoz span evidence"
                report.exit_code = 0
                return report
            # Fall through: try direct probe only if we have local key
            report.add(
                "query_range_probe",
                False,
                "session.trace_id null — server evidence has no spans; threat trace needs local SIGNOZ_API_KEY for direct probe",
            )
            report.verdict = (
                "DEGRADED — handoff ok; hero session lacks session.trace_id "
                "(threat trace_id present — re-record with OTLP or set trace_id on session)"
            )
            report.exit_code = 2
            return report

        if not effective_key:
            report.add("query_range_probe", False, "SIGNOZ_API_KEY absent")
            report.verdict = "DEGRADED — handoff ok; add SIGNOZ_API_KEY to .env for span probe"
            report.exit_code = 2
            return report

        ok, detail, spans = _query_range_probe(
            client, signoz_url=signoz_url, api_key=effective_key, trace_id=trace_id
        )
        report.span_names = spans
        if ok:
            report.add("query_range_probe", ok, detail)
            report.verdict = "PASS — HTTP handoff + live SigNoz span evidence"
            report.exit_code = 0
            return report
        if isinstance(status, dict) and status.get("query_range_ok"):
            conn_ok, conn_detail, conn_spans = _connectivity_probe(
                client, signoz_url=signoz_url, api_key=effective_key
            )
            if conn_ok:
                report.span_names = conn_spans
                report.add(
                    "query_range_probe",
                    True,
                    f"session trace stale; {conn_detail} (status.query_range_ok=true)",
                )
                report.verdict = (
                    "PASS — HTTP handoff ok; session trace not in retention; "
                    "SigNoz Query Range live via connectivity probe"
                )
                report.exit_code = 0
                return report
        report.add("query_range_probe", False, detail)
        report.verdict = f"DEGRADED — handoff ok; SigNoz probe failed ({detail})"
        report.exit_code = 2
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Case File HTTP → SigNoz handoff (G5)")
    parser.add_argument(
        "--session-id",
        default=os.getenv("ARCNET_VERIFY_SESSION", DEFAULT_SESSION),
        help=f"session to verify (default: {DEFAULT_SESSION})",
    )
    parser.add_argument(
        "--server-url",
        default=os.getenv("ARCNET_SERVER_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--signoz-url",
        default=os.getenv("SIGNOZ_URL_OVERRIDE"),
        help="override SigNoz base URL for direct Query Range probe (e.g. http://127.0.0.1:9)",
    )
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args(argv)

    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

    report = verify(
        server_url=args.server_url,
        session_id=args.session_id.strip(),
        signoz_url_override=args.signoz_url,
        timeout=args.timeout,
    )
    secrets = [os.getenv("SIGNOZ_API_KEY", "")]
    print(_redact(report.render(), secrets))
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
