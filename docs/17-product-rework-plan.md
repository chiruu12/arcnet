# ArcNet — Product rework plan (R1–R3)

Phased plan after founder review ([`16` §11](16-product-review-brief.md)). Goal: ship a **usable agent enhancement layer**, not a demo surface.

| Related | Role |
|---|---|
| [`16-product-review-brief.md`](16-product-review-brief.md) §11 | Founder decisions (authoritative) |
| [`15-product-map.md`](15-product-map.md) | Built inventory + gaps |
| [`12-data-api.md`](12-data-api.md) | Frozen wire contract — **additive only** |

**Standing constraints:** product-core never imports `agents/`/`scripts/`; Unplug in-process; no full tool outputs in agent contexts; local SigNoz path only; YAGNI on model-explorer fleet.

---

## Positioning (one line)

**ArcNet helps you make your agent work properly and enhance it** — observe → defend → replay → case file → improve (model/prompt evidence).

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

- [ ] No `demo` badge / “run demo fleet” empty copy in HQ user chrome.
- [ ] README leads with product positioning; “demo” only for bring-up script / limitations honesty.
- [ ] List endpoints accept `offset`; `X-Total-Count` correct under filters.
- [ ] `GET /api/agent-view/signals/{id}` returns envelope; 404 for unknown id.
- [ ] `GET /api/agent-view/check/{session_id}` returns envelope without `recorded_output` bodies.
- [ ] `GET /api/sessions?agent_id=&model=` filters correctly.
- [ ] `GET /api/agents/{id}/models` lists distinct models for that agent.
- [ ] Unit tests cover pagination headers, signals twin, session check, model filter.
- [ ] Import-boundary check still green.

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
| Hash / deep-links | Bookmarkable `#view` (+ optional `session` / `agent` query) so rehearsal and handoff work. |
| Empty states | Operator-facing: start server / seed / run scenario — not “demo toy” language. |
| Hero defaults | Prefer `s_ecfdb55d` / `s_2af44726` when they exist in the filtered set. |

### Acceptance criteria

- [ ] Case Files: changing agent resets model+session; changing model resets session; all three selects stay consistent with API filters.
- [ ] Time Machine uses the same cascade for session pick.
- [ ] Guidance visible on signals rows when set.
- [ ] `#case_files` / `#time_machine` (and peers) restore view on reload.
- [ ] HQ `pnpm build` / typecheck green.

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
- Scaffold shipped: `skills/arcnet-model-explore/SKILL.md` + `mcp-tools.json` (tool shapes only; no live catalog crawler).
- Prefer finishing R1/R2 over half-built explorers — **done for this PR**.

### Acceptance criteria (full R3 — later PR)

- [ ] Exploration agent can produce a recommendation note without calling kill/steer.
- [ ] MCP tools return bounded JSON; no full tool dumps.
- [ ] At least one Time Machine comparison path uses a current GPT-family candidate by default.
- [ ] Docs list pin changes if any SDK/provider deps move.

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
| 1 | Dashboard UUID deep-links | Later (unless cheap) |
| 14 | Corpus scorecard | Defer |
| — | Model explorer skills/MCP | **R3** |

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
