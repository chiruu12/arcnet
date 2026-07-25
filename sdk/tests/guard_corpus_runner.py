"""Offline guard corpus runner — measurement only (P14)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from unplug import Action, Guard, Source, TaintedText, TrustLevel

from arcnet.guard_factory import (
    build_guard,
    check_tool_call_with_content_guard,
    guard_verdict_from_result,
)

CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "guard_corpus.json"

BLOCK_ACTIONS = frozenset({Action.BLOCK, Action.REDACT, Action.REVIEW, Action.ABSTAIN})
Outcome = Literal["caught", "missed", "partial", "benign_ok", "untested"]


@dataclass
class CorpusObservation:
    entry_id: str
    class_name: str
    checkpoint: str
    expect: str
    known_gap: bool
    action: str
    risk_score: float
    rule: str | None
    category: str | None
    pattern_class: str | None
    outcome: Outcome
    findings_count: int = 0


@dataclass
class CorpusSummary:
    total: int
    caught: int
    missed: int
    partial: int
    benign_ok: int
    untested: int
    by_class: dict[str, dict[str, int]] = field(default_factory=dict)
    rules_fired: dict[str, int] = field(default_factory=dict)
    observations: list[CorpusObservation] = field(default_factory=list)


def _default_taint() -> TaintedText:
    return TaintedText(
        text="synthetic retrieved page with injected instruction",
        trust_level=TrustLevel.RETRIEVED,
        origin="fetch_url",
    )


def _scan_input(guard: Guard, payload: str, *, checkpoint: str) -> Any:
    source = Source.RETRIEVED if checkpoint == "retrieved" else Source.USER
    return guard.scan(payload, source=source)


def _scan_output(guard: Guard, payload: str) -> Any:
    return guard.scan_output(payload)


def _scan_tool_call(guard: Guard, entry: dict[str, Any]) -> Any:
    taint_sources = [_default_taint()] if entry.get("taint") else None
    return check_tool_call_with_content_guard(
        guard,
        entry["tool"],
        dict(entry.get("args") or {}),
        taint_sources=taint_sources,
    )


def _verdict_fields(result: Any, checkpoint: str) -> dict[str, Any]:
    verdict = guard_verdict_from_result(result, checkpoint=checkpoint)
    return {
        "action": str(getattr(result.action, "value", result.action)),
        "risk_score": float(result.risk_score or 0.0),
        "rule": verdict.get("rule"),
        "category": verdict.get("top_category"),
        "pattern_class": verdict.get("pattern_class"),
        "findings_count": len(result.findings or []),
    }


def _classify_outcome(
    *,
    expect: str,
    action: str,
    known_gap: bool,
) -> Outcome:
    blocked = action in {a.value for a in BLOCK_ACTIONS}
    if expect == "allow":
        return "benign_ok" if not blocked else "missed"
    if expect == "miss" or known_gap:
        return "missed" if not blocked else "caught"
    if expect == "block":
        if blocked:
            return "caught"
        return "missed"
    if expect == "partial":
        return "partial" if blocked else "missed"
    return "untested"


def run_entry(guard: Guard, entry: dict[str, Any]) -> CorpusObservation:
    checkpoint = entry["checkpoint"]
    turns = entry.get("turns")
    if turns:
        result = None
        for turn in turns:
            result = _scan_input(guard, turn, checkpoint=checkpoint)
        assert result is not None
    elif checkpoint == "tool_call":
        result = _scan_tool_call(guard, entry)
    elif checkpoint == "output":
        result = _scan_output(guard, entry["payload"])
    else:
        result = _scan_input(guard, entry["payload"], checkpoint=checkpoint)

    fields = _verdict_fields(result, checkpoint)
    outcome = _classify_outcome(
        expect=entry.get("expect", "block"),
        action=fields["action"],
        known_gap=bool(entry.get("known_gap")),
    )
    return CorpusObservation(
        entry_id=entry["id"],
        class_name=entry["class"],
        checkpoint=checkpoint,
        expect=entry.get("expect", "block"),
        known_gap=bool(entry.get("known_gap")),
        outcome=outcome,
        **fields,
    )


def load_corpus(path: Path | None = None) -> dict[str, Any]:
    corpus_path = path or CORPUS_PATH
    return json.loads(corpus_path.read_text(encoding="utf-8"))


def run_corpus(path: Path | None = None) -> CorpusSummary:
    corpus = load_corpus(path)
    observations: list[CorpusObservation] = []
    by_class: dict[str, dict[str, int]] = {}
    rules_fired: dict[str, int] = {}

    for entry in corpus["entries"]:
        guard = build_guard()
        obs = run_entry(guard, entry)
        observations.append(obs)

        class_bucket = by_class.setdefault(
            obs.class_name,
            {"caught": 0, "missed": 0, "partial": 0, "benign_ok": 0, "untested": 0, "total": 0},
        )
        class_bucket["total"] += 1
        class_bucket[obs.outcome] += 1

        if obs.rule and obs.outcome == "caught":
            rules_fired[obs.rule] = rules_fired.get(obs.rule, 0) + 1

    caught = sum(1 for o in observations if o.outcome == "caught")
    missed = sum(1 for o in observations if o.outcome == "missed")
    partial = sum(1 for o in observations if o.outcome == "partial")
    benign_ok = sum(1 for o in observations if o.outcome == "benign_ok")
    untested = sum(1 for o in observations if o.outcome == "untested")

    return CorpusSummary(
        total=len(observations),
        caught=caught,
        missed=missed,
        partial=partial,
        benign_ok=benign_ok,
        untested=untested,
        by_class=by_class,
        rules_fired=rules_fired,
        observations=observations,
    )


def attack_entries(summary: CorpusSummary) -> list[CorpusObservation]:
    """Payloads that expect a defensive response (exclude benign controls)."""
    return [o for o in summary.observations if o.expect != "allow"]


def headline_numbers(summary: CorpusSummary) -> dict[str, int]:
    attacks = attack_entries(summary)
    caught = sum(1 for o in attacks if o.outcome == "caught")
    missed = sum(1 for o in attacks if o.outcome == "missed")
    classes_total = len({o.class_name for o in attacks if o.class_name != "benign_control"})
    classes_with_miss = len(
        {
            o.class_name
            for o in attacks
            if o.outcome == "missed" and o.class_name != "benign_control"
        }
    )
    return {
        "attacks_total": len(attacks),
        "attacks_caught": caught,
        "attacks_missed": missed,
        "classes_total": classes_total,
        "classes_with_any_miss": classes_with_miss,
    }
