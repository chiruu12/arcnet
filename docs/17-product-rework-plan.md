# ArcNet — Product rework plan (R1–R3 + HQ Agent)

Phased plan after founder review ([`16` §11](16-product-review-brief.md)). Goal: ship a **usable agent enhancement layer**, not a demo surface.

| Related | Role |
|---|---|
| [`23-product-overview.md`](23-product-overview.md) | **Product overview** — enhancement-layer vision, HQ evolution, ~64% |
| [`20-honest-progress.md`](20-honest-progress.md) | **Measured scorecard** (authoritative readiness) |
| [`21-next-phases-plan.md`](21-next-phases-plan.md) · [`22-next-agent-packets.md`](22-next-agent-packets.md) | Next phases + packets (incl. **required TabFM**) |
| [`16-product-review-brief.md`](16-product-review-brief.md) §11 | Founder decisions (authoritative) |
| [`15-product-map.md`](15-product-map.md) | Built inventory + gaps |
| [`12-data-api.md`](12-data-api.md) | Frozen wire contract — **additive only** |
| [`18-hq-agent.md`](18-hq-agent.md) | HQ Agent maintenance layer (SigNoz reuse, MAD Griffin, versions, proposals) |
| [`19-path-to-95.md`](19-path-to-95.md) | Workstream catalog toward robustness (est. withdrawn; measure via `20`) |

**Standing constraints:** product-core never imports `agents/`/`scripts/`; Unplug in-process; no full tool outputs in agent contexts; local SigNoz path only; YAGNI on model-explorer fleet / auto-remediation.

---

## Positioning (one line)

**ArcNet is an agent enhancement layer** — observe → defend → replay → case file → improve (model/prompt evidence). Not a SigNoz clone; not demo theater. HQ = operator control plane (cascade, Fleet Health, Time Machine, Case File, HQ Agent).

**Honesty:** measured overall **~57% / ≤60%** ([`20`](20-honest-progress.md)). Prefer fix/test/measure over feature theater. Griffin = **MAD** now; **TabFM required Phase 7**; TabPFN deferred. HITL decide = SQLite today (AgentOS relay Phase 6). Apply confirm ≠ auth. MCP PARTIAL.

---

## Phase R1 — Product framing + API foundations

**Goal:** Remove demo-toy framing; close the API gaps that block real agent/HQ use.

### Scope

| Work | Notes |
|---|---|
| Strip user-facing “demo” copy | HQ chrome (`demo` tag), empty-state “run demo” hints, README tone that implies demo-only. Keep script names like `run-demo.sh` as bring-up commands; keep honest limitations. |
| Pagination on list endpoints | Additive `limit` + `offset` on sessions / signals / threats / sources / replays. Response body stays an **array** (docs/12 compat). Emit `X-Total-Count`, `X-Limit`, `X-Offset` headers. |
| Session filters for cascade | Additive `model` query on `GET /api/sessions` (with existing `agent_id`). |
| Agent models helper | Additive `GET /api/agents/{agent_id}/models` → `[{model, session_count, latest_started_at}]` for cascade UX. |
| Agent signals twin | Additive `GET /api/agent-view/signals/{id}` where `id` is `agent_id` or `session_id` — envelope with bounded signal rows (reason/guidance excerpts; no giant dumps). Extend docs/12 view enum. |
| Session check for agents | Additive `GET /api/agent-view/check/{session_id}` — compact status: session meta, threat/signal counts + top findings, timeline length, links. Bounded; no full tool payloads. |
| Document contract | Update `12` + map §4.2 for additive routes/params. |

### Acceptance criteria

- [x] No `demo` badge / “run demo fleet” empty copy in HQ user chrome.
- [x] README leads with product positioning; “demo” only for bring-up script / limitations honesty.
- [x] List endpoints accept `offset`; `X-Total-Count` correct under filters.
- [x] `GET /api/agent-view/signals/{id}` returns envelope; 404 for unknown id.
- [x] `GET /api/agent-view/check/{session_id}` returns envelope without `recorded_output` bodies.
- [x] `GET /api/sessions?agent_id=&model=` filters correctly.
- [x] `GET /api/agents/{id}/models` lists distinct models for that agent.
- [x] Unit tests cover pagination headers, signals twin, session check, model filter.
- [x] Import-boundary check still green.

---

## Phase R2 — HQ information architecture

**Goal:** Tightly coupled flows that match how operators actually pick work.

### Scope

| Work | Notes |
|---|---|
| Case Files cascade | **Agent → LLM+version → Session ID** wired to fleet + models + filtered sessions. Prefer hero sessions when present after cascade resolves. |
| Time Machine cascade | Same cascade pattern for replayable sessions (`has_transcript`). Candidate model defaults to a current reliable GPT-family id (editable). |
| Signals guidance | Render `guidance` when present (column or secondary line). |
| Agent mode signals | Use `/api/agent-view/signals/…` envelope (not raw list). |
| Hash / deep-links | Bookmarkable `#view` (+ optional `session` / `agent` / `model` query) so rehearsal and handoff work. |
| Fleet drill-down | Fleet cards + sidebar mini-fleet navigate to `#case_files?agent=` / `#signals?agent=`. |
| SigNoz UUID deep-links | `/api/signoz/status` returns `dashboards` (env override or title resolve); HQ opens `/dashboard/{uuid}`. |
| Session tools (SDK) | `arcnet.hq` helpers for check / signals / session / incident / sources — bounded envelopes only. |
| Empty states | Operator-facing: start server / seed / run scenario — not “demo toy” language. |
| Hero defaults | Prefer `s_ecfdb55d` / `s_2af44726` when they exist in the filtered set. |

### Acceptance criteria

- [x] Case Files: changing agent resets model+session; changing model resets session; all three selects stay consistent with API filters.
- [x] Time Machine uses the same cascade for session pick.
- [x] Guidance visible on signals rows when set.
- [x] `#case_files` / `#time_machine` (and peers) restore view on reload; optional `?agent=&model=&session=` preserved.
- [x] Fleet drill-down + sidebar agent → case_files / signals.
- [x] SigNoz dashboard UUID deep-links when IDs available (env or status resolve).
- [x] SDK session tools for check/signals/session agent-views.
- [x] HQ `pnpm build` / typecheck green.

### Manual try (Case File cascade)

```bash
./scripts/run-demo.sh   # or existing server + seeded DB
# open http://localhost:5173/#case_files
# 1) pick agent_j → 2) pick model (e.g. gpt-4o-mini) → 3) pick session (prefer Edgar)
# export_case_file() downloads zip
```

---

## Phase R3 — Model performance + exploration (scaffold)

**Goal:** Spec + thin skills/MCP surface for **exploration-only** model discovery. Do not ship a full autonomous fleet.

### Product intent

- Run Time Machine / sims against **current reliable models**; show which perform better for a job class (security resist, loop break, cost).
- **Exploration agents** periodically fetch/compare model options for task types (chat, tool-heavy, long-context, cheap batch) — report only; humans/coding agents apply changes.
- Expose discovery via **skills** + **MCP tools** so Cursor/Claude can ask “what should I try next for this incident?”

### Spec — exploration agent (not ops)

| Concern | Decision |
|---|---|
| Autonomy | Explore + write recommendations; **never** mutate live agent config or kill/steer production without human/coding-agent action. |
| Inputs | Task type tags, recent Case Files / replay verdicts, provider model catalogs (HTTP). |
| Outputs | Ranked `{model, reason, evidence_refs[]}` stored as notes/signals (`kind=note`, `source=model_explorer`) or a future table. |
| Cadence | Periodic job (cron / server loop) — optional env flag; off by default. |

### Skills + MCP tool shapes (target)

Skills package (proposed path: `skills/arcnet-model-explore/` or repo `mcp/model-explore/`):

| Tool | Args | Returns |
|---|---|---|
| `list_task_types` | — | Known usage buckets |
| `recommend_models` | `{task_type, constraints?}` | Ranked candidates + rationale |
| `compare_replay_verdicts` | `{session_id}` or `{scenario}` | Which candidate models won which dimensions |
| `fetch_provider_catalog` | `{provider}` | Newest/reliable ids (cached; no secrets in spans) |

### This-pass deliverable

- Spec above stays in this doc.
- Thin implementation: `skills/arcnet-model-explore/` + `sdk/arcnet/model_explore.py` (curated OpenAI snapshot, recommend/compare/record, MCP stdio shim).
- Default Time Machine candidate remains `gpt-4o`.

### Acceptance criteria (full R3 — later PR)

- [x] Exploration agent can produce a recommendation note without calling kill/steer.
- [x] MCP tools return bounded JSON; no full tool dumps.
- [x] At least one Time Machine comparison path uses a current GPT-family candidate by default.
- [ ] Docs list pin changes if any SDK/provider deps move.

---

## Phase HQ — Operator maintenance agent (next after R2)

**Goal:** Complete the overall fix/enhancement layer as a real agent operators (and coding agents) can run — reuse SigNoz + ArcNet APIs; add version timelines and model-change **proposals** only.

Full design: [`18-hq-agent.md`](18-hq-agent.md).

### Scope (slice 1)

| Work | Notes |
|---|---|
| Spec | SigNoz reuse inventory; tool list; version schema; Unplug placement |
| SDK tools | `arcnet.hq_tools` — HTTP wrappers (fleet, check, signals, signoz, griffin MAD, versions, propose) |
| Registry | Additive `agent_versions` + list/create/timeline APIs |
| Agent | `agents/hq_agent/` Agno definition + Unplug guards; tools call SDK only |
| UI | Thin `#hq_agent` panel — proposals + run instructions |
| Skills/MCP | `skills/arcnet-hq-agent/` |

### Acceptance criteria

- [x] Docs/18 covers reuse vs build; Griffin labeled **MAD** (not TabFM).
- [x] Version registry APIs + tests green.
- [x] HQ tools return bounded JSON; import boundary green.
- [x] HQ agent wires Unplug like other fleet agents.
- [x] Propose-model writes `source=hq_agent` note — does not auto-apply.
- [x] Case File / replay tools on HQ agent (`case_file_view`, `replay_compare`).
- [x] Proposal inbox uses `source=hq_agent` filter + human-gated apply UI.
- [x] `POST /api/agents/{id}/apply-model` requires `confirm: true` and records version bump.
- [x] Optional `session_id` on version register / apply pins `sessions.agent_version`.

---

## Honesty: checklist ≠ product-ready

Acceptance criteria above measure **surface existence**, not production-usable robustness. Founder-critical re-score started near **~48%**; after Phases 2–4 the **authoritative measured overall is ~57% / ≤60%** ([`20-honest-progress.md`](20-honest-progress.md)). Do not cite 74/80/95 theater.

| Area | Robustness (0–100) | Note |
|---|---:|---|
| Positioning / framing | 58 | Enhancement-layer docs aligned; demo script still mixed |
| HQ frontend | 64 | Cascade + hash + pagination labels; polish open |
| Human APIs | 66 | Pagination + write secret; HITL ≠ AgentOS relay |
| Agent APIs / tools | 66 | Envelopes + timeouts; twins incomplete |
| HQ Agent | 62 | Propose→apply→pin CI + dry-run; live restart operator |
| Version timeline / pinpoint | 68 | Pin + check narrative; cascade polish open |
| Model explore / sims | 56 | TM session-scoped; explore scaffold |
| Griffin (MAD) | 54 | MAD cold soak; **TabFM required Phase 7 — not coded** |
| SigNoz | 58 | Provision + probe; MCP PARTIAL |
| Unplug coverage | 70 | Fleet + HQ Agent; matrix → Phase 5 |
| Tests / CI | 58 | Phase 2 exits met |
| Hackathon ship assets | 35 | Screenshots/video open — **excluded from overall** |

**Overall ~57%** (cap ≤60%). Checklist completion ≠ “done product.” See [`20`](20-honest-progress.md) for measured cells and exits.

### Robustness backlog (impact order)

1. Phase 5 safety matrix + honesty chrome ([`22`](22-next-agent-packets.md))
2. Phase 6 HITL UI + api_down recover (after Phase 5)
3. **TabFM Phase 7 required** (`google/tabfm-1.0.0-pytorch` `regression/`; MAD degrade)
4. Auth / abuse surface beyond optional secrets (still localhost trust)
5. Model explore tied to TM verdicts (empirical)
6. Hackathon capture assets if still submitting

**Next:** [`21-next-phases-plan.md`](21-next-phases-plan.md) · [`22-next-agent-packets.md`](22-next-agent-packets.md). Overview: [`23`](23-product-overview.md).

### Wave tracking (honest)

| Wave | Status | Measured overall |
|---|---|---|
| Baseline | founder re-score | **~48%** |
| A — Foundations | merged | surfaces landed; do not claim 95% |
| B — Enhancement loop | landed | partial — **do not claim 95%** |
| Phases 2–4 | exits met | **~57% / ≤60%** ([`20`](20-honest-progress.md)) |
| C / Phase 5+ | next | packets in [`22`](22-next-agent-packets.md) |

Griffin = **MAD** only until Phase 7. No TabFM-live claims. TabPFN deferred.
---

## Priority vs old map §6

| Old # | Area | R-phase |
|---|---|---|
| — | Demo framing removal | **R1** |
| — | Pagination / agent signals / session check | **R1** |
| 3 / 2 | Case File + TM pickers (cascade) | **R2** |
| 4 | Signals `guidance` | **R2** |
| 7 | HQ routing | **R2** |
| 12 | Agent-view consistency (signals) | **R1–R2** |
| 1 | Dashboard UUID deep-links | **R2** (status + env) |
| 14 | Corpus scorecard | Defer |
| — | Model explorer skills/MCP | **R3** |
| — | HQ Agent / version timeline / proposals | **HQ** ([`18`](18-hq-agent.md)) |

---

## Verification checklist (this rework PR)

```bash
PYTHONPATH="sdk:server" uv run python -m unittest discover -s server/tests
uv run python scripts/check_import_boundaries.py
cd hq && pnpm build
```

Manual: Case File cascade steps in R2 above.

---

## Out of scope

- SigNoz Cloud
- Full autonomous ops / evolver agents
- Breaking changes to existing JSON array list bodies without a version bump
- Pin bumps unless required for model work (document if they happen)
