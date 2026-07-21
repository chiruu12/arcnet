# ArcNet — Unplug Integration

## Ground rules

- Consume **`unplug-ai==0.5.2` from PyPI** as a normal dependency — never vendor its code into this repo (hackathon "no prior work" rule: ArcNet is the build; unplug-ai is a published library we use, same as Agno).
- The local `unplug-v1` checkout is a **diverged old branch (0.2.0, ~228 commits behind)** — do not code against it. Use the PyPI package; read upstream `origin/main` source only for reference.
- **Phase-0 smoke test PASSED (2026-07-21)** — first test = exact S1 taint chain. Confirmed against installed `unplug-ai==0.5.2`:
  - Exports: `Guard, ScanResult, Finding, Action, Source, TaintedText, TrustLevel, GuardConfig` (+ `Action.ABSTAIN` exists — was missing from earlier docs).
  - `scan` / `scan_output` / `check_tool_call` / `notify_taint_source` / `wrap_for_context` / `add_canary` / `with_tiny` / `metrics` all present with signatures recorded below.
  - **S1 chain (the load-bearing path):** `scan(poisoned, RETRIEVED)` → `action=block` (injection findings) → `wrap_for_context` + `notify_taint_source("fetch_url", origin="retrieved")` → `check_tool_call("send_email", args, taint_sources=[TaintedText(...)])` → **`action=block`** (`retrieved_source_in_side_effect` score 0.85).
  - **Doc-vs-reality drift (fixed here):** session-taint alone (`notify_taint_source` without passing `taint_sources=`) yields **`action=review`** at default `tools.tainted_side_effect_review_score=0.35`, not block. ArcNet must pass `taint_sources=[TaintedText(text=…, trust_level=TrustLevel.RETRIEVED, origin="fetch_url")]` into `check_tool_call` (or raise that score ≥ 0.8) for the Edgar exfil to hard-block.

## Role in ArcNet: source-trust monitoring (the spine, not a bolt-on)

In v2, Unplug *is* the provenance/trust layer, not a side scanner. The framing:
- Every datum an agent ingests carries a **trust level** (`user` · `retrieved`/`scraped` · `tool_output` · `external` · `system`) — this is Unplug's native `TrustLevel`/taint model.
- Unplug scans the **untrusted** sources, because that's where injection enters. **Scraped/fetched content is filtered before it reaches the model.**
- **Forward-facing agents** (those that ingest third-party content) are flagged higher injection-risk — ArcNet sets `arcnet.exposure=forward_facing` on the agent and surfaces it in Fleet Health.
- Taint **propagates**: untrusted content flowing toward a sensitive tool (email/DB/payment) blocks that tool call (the Edgar exfil chain).
- Homogeneous with observability: "source trust" and "injection exposure" are health dimensions next to cost and latency — one product.

The Time Machine replays through the same `UnplugGuardrail`, so trust checks apply identically to baseline and candidate — the counterfactual isolates the *model's* behavior, not the guard's.

## What unplug-ai actually is (design for this, not the README)

A fast, CPU-only guard: regex scanner families + normalization + taint tracking, with optional ML and an optional bring-your-own LLM judge. Sub-ms to low-ms per scan — cheap enough to run at **every** checkpoint and emit as telemetry. No server or MCP needed; pure in-process. Its taint/trust model (`TrustLevel`, `TaintedText`, `Tagger`, `notify_taint_source`, `wrap_for_context`) is exactly what the source-trust spine needs.

**Phase-4 placement decision:** keep Unplug in-process. Its checks are synchronous control-flow gates and its taint state is session-local; a separate service would add network latency and availability risk to the path that must block a dangerous tool call. vLLM is not applicable: Unplug is a guard/scanner library, not an autoregressive language model server. The optional LLM judge remains P2 and, if ever enabled, may call a provider or compatible LLM endpoint without moving the core guard out of process.

## Core contract (Phase 0 confirmed on installed `unplug-ai==0.5.2`)

```python
from unplug import Guard, GuardConfig, ScanResult, Finding, Action, Source, TaintedText, TrustLevel

guard = Guard()                                  # config via GuardConfig if needed
res: ScanResult = guard.scan(text, source=Source.USER)
res = guard.scan_output(text)                    # secrets/PII on outputs → redacted_text
res = guard.check_tool_call(
    tool_name, arguments,
    taint_sources=[TaintedText(text=page, trust_level=TrustLevel.RETRIEVED, origin="fetch_url")],
)
```

**Signatures (installed):**
- `scan(text: str, source: Source | str = USER) -> ScanResult`
- `scan_output(text: str | TaintedText) -> ScanResult`
- `check_tool_call(tool_name: str, arguments: dict, *, taint_sources: list[TaintedText] | None = None, approved: bool | None = None) -> ScanResult`
- `notify_taint_source(tool_name: str, *, origin: str = "") -> None`
- `wrap_for_context(text: str, source: Source | str = RETRIEVED) -> str`  # returns tagged string, not TaintedText
- `add_canary(prompt: str, *, label: str = "system_prompt") -> str`
- `with_tiny(*, auto_download: bool = True, require_ml: bool = False, **kwargs) -> Guard`

`ScanResult`: `safe`, `action`, `risk_score`, `findings`, `redacted_text`, `latency_ms`, `stages_run`, plus Phase-0 extras: `degraded`, `degraded_layers`, `approval` (populated on `review` for side-effect tools).
`Finding`: `category`, `subcategory`, `stage`, `span_start`/`span_end`, `score`, `evidence`, `replacement`.
`Action`: `allow` | `redact` | `abstain` | `block` | `review` (note **`abstain`** — not in earlier draft).
`Source`: `user` | `retrieved` | `tool_output` | `system` (no separate `external` on Source; use `TrustLevel.EXTERNAL` on `TaintedText`).
`TrustLevel`: `trusted` | `user` | `retrieved` | `tool_output` | `external` | `unknown`.
Policy defaults: `block_threshold=0.8`, `redact_threshold=0.5`, `review_threshold=0.3`. Tool policy: `tainted_side_effect_review_score=0.35` (session-taint → review); pass `taint_sources` for side-effect tools to get score 0.85 → block.

Additional surface confirmed: `guard.metrics` (`MetricsCollector`), `guard.add_canary`, `Guard.with_tiny(...)`.

## Checkpoint → ArcNet mapping (Agno integration points)

Packaged as **four checkpoint callables from one shared `Guard`** — Agno's four surfaces have four *different* signatures (input `BaseGuardrail` subclass is input-only by design; per-tool `post_hook`; agent-level `tool_hooks` middleware; plain `post_hooks` output function — there is no output-guardrail class). Named distinctly in `arcnet/guardrail.py` so the mismatch is a design-time fact (`02`). Still idiomatic Agno, and a future OSS-contribution candidate to Agno itself. Note: Agno ships its own basic guardrails (PII / prompt-injection) — position Unplug as the deeper layer (12-stage normalizer catches obfuscated attacks — leetspeak/homoglyph/base64; taint tracking; canaries) and say so in the README comparison table.

| Agent moment | Agno hook | unplug call | On non-allow |
|---|---|---|---|
| User message enters | `BaseGuardrail` subclass (input-only by signature) | `scan(text, USER)` | block → guardrail error, refuse turn (S5) |
| `fetch_url` / retrieval returns | per-tool `@tool(post_hook=…)` on retrieval tools | `scan(text, RETRIEVED)` + `wrap_for_context` + `notify_taint_source` | block → drop content, note to agent |
| Tool about to execute | agent-level `tool_hooks=[…]` middleware (all tools; must call `func(**args)`) | `check_tool_call(name, args, taint_sources=[…])` | block → cancel call, steer signal (S1/S3); session-taint alone is `review` — pass `TaintedText` for hard block |
| Final answer leaves | `post_hooks=[…]` function on `RunOutput` (no guardrail class exists for output) | `scan_output(text)` | redact → ship `redacted_text` + neuralyzer event (S2) |

Every call (clean or not) → one `arcnet.guard` span + metrics (see `04-signoz-integration.md`). Findings → span events + structured logs. `block` → span status ERROR.

**Trust-model gotcha (by design, don't misread as a miss):** `leakage` only fires on non-user sources / outputs; `harmful` only on `tool_output`/`retrieved`/`external`. Plain `scan(text)` on user input detects injection/destructive only. Scenario assertions must pass the right `Source`.

**False-positive gotcha:** the `base64_payload` injection pattern is broad (any long base64-ish run) — keep JWTs/long tokens out of fixture content, or expect `review` flags (which is itself a fine beat: triage in the UI).

## Attack fixtures

- Lift labeled samples from the installed package's benchmark module (12 injection incl. DAN/system-extraction + benign hard-negatives, 6 destructive, 4 leakage) — check its import path on 0.5.2 (`unplug` benchmarks or sdk extras).
- Hand-write S1's poisoned web pages (llmail-inject style indirect injections: HTML comments, hidden divs, "forward the last customer record to…"). These are ours, in `agents/scenarios/fixtures/`.
- PII seeds: fake customers (name/email/SSN-format) in the demo "database".

## Stretch (F10): LLM judge

`Guard(judge=CallableJudge(...))` with a cheap model for the borderline band (0.3–0.8): borderline → judge verdict as an extra `judge` finding stage — shows layered defense in the trace (regex stage ms → judge stage ~1s, visible as child span latency). Only if P0/P1 are done.
