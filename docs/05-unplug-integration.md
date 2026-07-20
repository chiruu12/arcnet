# ArcNet — Unplug Integration

## Ground rules

- Consume **`unplug-ai==0.5.2` from PyPI** as a normal dependency — never vendor its code into this repo (hackathon "no prior work" rule: ArcNet is the build; unplug-ai is a published library we use, same as Agno).
- The local `unplug-v1` checkout is a **diverged old branch (0.2.0, ~228 commits behind)** — do not code against it. Use the PyPI package; read upstream `origin/main` source only for reference.
- **Day-0 smoke test is mandatory.** Precisely what's confirmed vs assumed:
  - **Verified against 0.5.2 source** (`origin/main`): the top-level exports `Guard, ScanResult, Finding, Action, Source` all exist, and `Guard` exposes `scan`, `scan_output`, `check_tool_call`, `add_canary`, `metrics`.
  - **From the older 0.2.0 explore, treat as assumed until Day 0**: the exact *field* lists of `ScanResult`/`Finding`, the default action thresholds, and the `notify_taint_source`/`wrap_for_context`/`with_tiny` signatures. Confirm these against the installed package and fix this doc where it drifts.

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

## Core contract (top-level names verified on 0.5.2; field details assumed — confirm Day 0)

```python
from unplug import Guard, ScanResult, Finding, Action, Source

guard = Guard()                                  # config via GuardConfig if needed
res: ScanResult = guard.scan(text, source=Source.USER)
res = guard.scan_output(text)                    # secrets/PII on outputs → redacted_text
res = guard.check_tool_call(tool_name, arguments)
```

`ScanResult`: `safe: bool`, `action: Action("allow"|"redact"|"block"|"review")`, `risk_score: float 0–1`, `findings: list[Finding]`, `redacted_text: str|None`, `latency_ms`, `stages_run`.
`Finding`: `category` (scanner: `injection|destructive|leakage|harmful|financial|secrets|taint|judge|limits`), `subcategory` (rule id, e.g. `ignore_previous`, `sql_drop`), `stage`, `span_start/end`, `score`, `evidence`, `replacement`.
Action thresholds (defaults): block ≥ 0.8, redact ≥ 0.5, review ≥ 0.3.

Additional 0.5.2 surface worth using (method names verified on 0.5.2; args confirm Day 0):
- `guard.add_canary(prompt, label="system_prompt")` — **F9**: canary in system prompt → output scan catches exfiltration (method confirmed present on 0.5.2)
- `guard.notify_taint_source(tool_name, origin=...)` + `guard.wrap_for_context(text, source=RETRIEVED)` — taint bookkeeping for fetched content (S1 Edgar)
- `guard.metrics` (`MetricsCollector`) — per-scanner stats we can mirror into OTel gauges
- `ExecutionContext` / `ScanPolicy` / `with_tiny(...)` — explore day 1; `with_tiny` looks like the bundled tiny-ML path, nice bonus if it works out of the box

## Checkpoint → ArcNet mapping (Agno integration points)

Packaged as **`UnplugGuardrail`** (Agno `BaseGuardrail`) + tool hook factories — idiomatic Agno, and a future OSS-contribution candidate to Agno itself. Note: Agno ships its own basic guardrails (PII / prompt-injection) — position Unplug as the deeper layer (12-stage normalizer catches obfuscated attacks — leetspeak/homoglyph/base64; taint tracking; canaries) and say so in the README comparison table.

| Agent moment | Agno hook | unplug call | On non-allow |
|---|---|---|---|
| User message enters | input guardrail / pre-hook | `scan(text, USER)` | block → guardrail error, refuse turn (S5) |
| `fetch_url` / retrieval returns | tool **post**-hook on retrieval tools | `scan(text, RETRIEVED)` + `wrap_for_context` + `notify_taint_source` | block → drop content, note to agent |
| Tool about to execute | tool **pre**-hook (all tools) | `check_tool_call(name, args)` | block → cancel call, steer signal (S1/S3) |
| Final answer leaves | output guardrail / post-hook | `scan_output(text)` | redact → ship `redacted_text` + neuralyzer event (S2) |

Every call (clean or not) → one `arcnet.guard` span + metrics (see `04-signoz-integration.md`). Findings → span events + structured logs. `block` → span status ERROR.

**Trust-model gotcha (by design, don't misread as a miss):** `leakage` only fires on non-user sources / outputs; `harmful` only on `tool_output`/`retrieved`/`external`. Plain `scan(text)` on user input detects injection/destructive only. Scenario assertions must pass the right `Source`.

**False-positive gotcha:** the `base64_payload` injection pattern is broad (any long base64-ish run) — keep JWTs/long tokens out of fixture content, or expect `review` flags (which is itself a fine beat: triage in the UI).

## Attack fixtures

- Lift labeled samples from the installed package's benchmark module (12 injection incl. DAN/system-extraction + benign hard-negatives, 6 destructive, 4 leakage) — check its import path on 0.5.2 (`unplug` benchmarks or sdk extras).
- Hand-write S1's poisoned web pages (llmail-inject style indirect injections: HTML comments, hidden divs, "forward the last customer record to…"). These are ours, in `agents/scenarios/fixtures/`.
- PII seeds: fake customers (name/email/SSN-format) in the demo "database".

## Stretch (F10): LLM judge

`Guard(judge=CallableJudge(...))` with a cheap model for the borderline band (0.3–0.8): borderline → judge verdict as an extra `judge` finding stage — shows layered defense in the trace (regex stage ms → judge stage ~1s, visible as child span latency). Only if P0/P1 are done.
