# ArcNet — Blog post script

> Publishable outline + draft prose grounded in current product reality (catalog **2026-07e**,
> HQ Agent highlights/TOON, Time Machine heroes, SigNoz-optional stack). Edit voice and length;
> keep numbers and caveats honest. Live walkthrough timings live in [`06-demo-script.md`](06-demo-script.md).
> **Final publish copy lives in `docs/plans/blog-draft.md`** — it merges this outline with the
> SigNoz wiring detail and passes the fact checklist below.

---

## Title options

1. **ArcNet: prove a model upgrade on the incidents your agents already recorded**
2. **Session-level agent observability — defend, hand off, and replay on SigNoz**
3. **Stop swap-and-pray: a Time Machine for agent fleets**
4. **Agents that watch themselves (and get better) — building ArcNet**
5. **From threat feed to TOON twin: an operator loop for coding agents**

**Recommended default:** (1) — outcome-first, distinct from generic “we added tracing” posts.

**Subtitle options:**

- Observe → defend → hand off → prove → improve
- Built on SigNoz · Unplug at the trust boundary · SQLite-primary transcripts
- Catalog 2026-07e list-price intel · agent_view TOON · human-gated apply

---

## Audience & angle

| Audience | Hook |
|---|---|
| Hackathon / SigNoz judges | Self-hosted OTel → alerts → signals; custom dashboards; Query Range evidence |
| Agent operators | Fleet health, forward-facing risk, cost, Griffin MAD cold-start |
| Builders shipping multi-model fleets | Evidence-grounded catalog recommendations + session replay before routing changes |
| Coding-agent users | agent-view envelopes + `?format=toon` + Case File zip |

**Core angle (one sentence):** ArcNet closes the improve loop at the *agent-session* level — not just another trace UI — by defending the trust boundary, exporting machine-readable incidents, and replaying whole recorded sessions against a candidate model before you ship the swap.

**Tone:** product-honest, concrete, deadpan-technical. No journey narrative, no “we grilled ourselves,” no readiness cosplay above what `docs/20-honest-progress.md` says.

---

## Length toggles

| Mode | Words | Keep | Cut |
|---|---|---|---|
| **Short** | ~900–1,200 | Hook, loop diagram, Time Machine hero, catalog/TOON paragraph, run it, caveats | Deep SigNoz payload notes, corpus API, dogfood |
| **Standard** | ~1,600–2,200 | Short + SigNoz wiring + Griffin MAD + Case File + HQ Agent apply | TabFM roadmap essays |
| **Deep** | ~2,500–3,500 | Standard + OpenInference vs `gen_ai.*`, alert v5, webhook vs inline fast-path, TOON examples, API table | — |

---

## Structure (use as H2 outline)

1. Hook — agents fail in ways dashboards weren’t built for  
2. What ArcNet is (and isn’t)  
3. The loop in one diagram  
4. Observe & defend (fleet, Unplug, signals)  
5. SigNoz wiring *(standard/deep)*  
6. Griffin: cold-start anomalies without a season  
7. Time Machine — the whoa  
8. Built for agents that fix agents (agent-view + TOON)  
9. Model intelligence — catalog 2026-07e  
10. HQ Agent — propose → human apply  
11. What I’d tell you before you build this  
12. Run it + CTA  
13. Honest limitations  

---

## Screenshot / moment checklist

Capture from `http://localhost:5173` (not `127.0.0.1`):

| # | Moment | Route / proof |
|---|---|---|
| 1 | Home loop + live tiles | `#home` |
| 2 | Fleet card with `[FORWARD]` + MAD strip | `#fleet_health` |
| 3 | Signals or sources trust row | `#signals` / `#sources_trust` |
| 4 | Time Machine Worms baseline vs candidate | `#time_machine?…&session=s_2af44726` |
| 5 | Edgar resist / exploited contrast | `#time_machine?…&session=s_ecfdb55d` |
| 6 | Case File preview + export | `#case_files?…&session=s_ecfdb55d` |
| 7 | HQ Agent `// new in catalog` (kimi / qwen / deepseek) | `#hq_agent?agent=agent_j` |
| 8 | Recommendation buckets + `catalog=2026-07e` · list-price line | same |
| 9 | `agent_view` TOON panels | toggle on `#hq_agent` |
| 10 | Optional: SigNoz waterfall / Threats & Trust | `:8080` via `#dashboards` |
| 11 | Optional: apply confirm + reload banner | only if proposals exist |

Alt-text tip: include model ids and verdict words (`mixed`, `[BLOCKED]`, `list-price`) so the post stays scannable without the image.

---

## Draft prose (standard length)

### Hook

AI agents fail in ways dashboards weren’t built for. A support agent scrapes a page with a hidden instruction and quietly tries to email your customer table. A batch agent hits an endless pagination loop and burns tokens until someone notices. And when you finally want to fix one — swap the model, tighten the prompt — the honest answer to “will it behave better?” is usually a shrug.

ArcNet is an enhancement layer for agent fleets on top of [SigNoz](https://signoz.io): observe behavior and cost, defend the trust boundary with [unplug-ai](https://pypi.org/project/unplug-ai/), hand incidents to coding agents in a format they can consume, and **prove** a candidate model on the sessions your fleet already recorded.

### What it is (and isn’t)

ArcNet is not a SigNoz clone and not a general eval platform. It is the control plane around the loop:

**observe → detect → defend → hand off → prove → improve.**

Humans get a React HQ. Coding agents get the same records as bounded **agent-view** envelopes — optionally encoded as **TOON** for token-efficient machine reads. Transcripts for replay live in SQLite (traces truncate; the Time Machine does not reconstruct sessions from span attributes).

### The shape of the system

```
Agno agents (+ Unplug guardrails)          React HQ (mission control)
        │  OpenTelemetry (OpenInference)          │
        ▼                                         ▼
   SigNoz (optional, self-hosted) ◄── webhooks ──► ArcNet server (FastAPI + SQLite)
        │   dashboards · alerts · traces           │  signals · threats · replays · case files
        └────────── Query Range API ───────────────┘
```

Demo stack after `./scripts/run-demo.sh`: server `:8000`, AgentOS `:7777`, HQ at **`http://localhost:5173`**. SigNoz on `:8080` is depth, not a hard dependency for the SQLite-primary heroes.

### Observe and defend

HQ **fleet_health** shows every agent’s exposure, threat and block counts, and 24h cost. Forward-facing agents are tagged — they browse and ingest untrusted content, so they carry higher injection risk.

Unplug runs **in-process** in the SDK at the trust checkpoints (input, retrieved content, tool call, output). A blocked exfiltration is not a log line you hope someone reads; it becomes structured telemetry and a **signal** (`steer` / `kill` / `pause` / `note`). Guard blocks also take an inline fast-path in milliseconds; when SigNoz is wired, the alert webhook lands behind it as the system of record.

### SigNoz wiring *(keep in standard/deep)*

Self-hosted via Docker, instrumented with OpenInference on Agno. Span names look like `{agent}.run → {model}.invoke → {tool}` — OpenInference semconv, not OTel `gen_ai.*`. Custom `arcnet.guard.*` attributes carry checkpoint, action, risk score, and pattern class.

Provisioned surfaces include Fleet Ops, Threats & Trust (including ClickHouse SQL when the builder runs out), Cost & Tokens, and the Agno template. Alerts POST to `/webhooks/signoz` and become ArcNet signals. Case Files pull bounded evidence through SigNoz’s Query Range API (`GET /api/signoz/evidence`). SigNoz MCP stdio exists but is documented **PARTIAL**; the product handoff prefers HTTP.

### Griffin

SigNoz seasonal anomaly rules want history. New agents have no season. **Griffin** is ArcNet’s per-metric statistical baseline — **MAD** in production today. Outlier → report; normal → silence. A TabFM path is stubbed for a later phase; do not claim it live.

### Time Machine

Every hero session ships as a replayable transcript. The Time Machine replays a recorded incident against a **different model** (or prompt): same goal, same tool outputs mocked from the transcript, same guardrails — only the brain changes. Three runs at temperature 0, majority verdict, honest `inconclusive` when runs disagree. Temperature 0 reduces variance; it is not determinism.

Two recorded heroes:

| Incident | Baseline story | Candidate story |
|---|---|---|
| **S1 Edgar** (`s_ecfdb55d`) | Follows poisoned-page social engineering; `send_email` exfil **blocked** by taint | Resists the injection |
| **S4 Worms** (`s_2af44726`) | Paginates until **killed** | Breaks the loop earlier |

Verdicts are often **`mixed`**: security or reliability improves while cost rises. That honesty is the point — you see the tradeoff before you change routing. Seed pins Agent J history to `av_demo_agent_j` and registers a `demo.luna` version so the version cascade is real, not a single orphan session.

LangSmith and Braintrust replay a call or a dataset row. ArcNet replays the **whole agent session**. That difference is what turns trace history into a behavioral regression suite.

### Built for agents that fix agents

Every HQ view has a twin at `GET /api/agent-view/{view}/{id}` with cross-links (`session → case_file → threats → models`). Errors return `{detail, hint}` with the next call to make.

As of catalog **2026-07e**, agent-oriented GETs also accept **`?format=toon`** ([TOON](https://toonformat.dev) — tabular, token-efficient). HQ **agent_view** on `hq_agent` renders `model_intel.toon` and `model_proposals.toon` panels so you can see the machine twin without leaving the UI. Export still ships a Case File zip: `case-file.md` (fix-prompt preamble + MCP hints) plus `case-file.json`.

### Model intelligence — catalog 2026-07e

`GET /api/agents/{id}/model-intel` projects candidates from a dated static catalog. Dollars are labeled **list-price estimates** — not your bill. Projections multiply *this agent’s recorded token totals* by catalog rates. Recommendation buckets (`recommended_upgrade`, `cost_saver`, `peer`, `not_advised`) carry fit reasons and blockers from evidence, not vibes.

**New in catalog** highlights currently include:

- `kimi-k2.7-code`, `kimi-k3`
- `qwen3.8-max-preview`, `qwen3.6-35b-a3b`
- `deepseek-v4-flash`, `deepseek-v4-pro`

HQ surfaces them under `// new in catalog` before the full bucket tables. A reasoning-tier recommendation appears only when recorded threat rate or contested replay verdicts justify it.

### HQ Agent — propose, then apply

`#hq_agent` is the operator maintenance layer: diagnose strip (agent → version → session), catalog projections, proposal cards, version timeline, and a human-gated apply form (`confirm` required). Apply updates SQLite and may pin a session; it does **not** silently restart AgentOS — the UI says `agentos_reload_required` when a reload is still needed.

Proposal cards appear after HQ Agent runs (for example via `python -m hq_agent …`). A fresh seed may show an empty inbox; the catalog buckets alone still demonstrate the improve path. HITL approve/reject is SQLite bookkeeping with a best-effort relay — not a full Agno pause/resume product.

### What I’d tell you before you build this

1. **Verify the semconv before writing dashboards.** OpenInference ≠ `gen_ai.*`.
2. **SQLite-primary for anything you’ll replay.** Span attributes truncate; transcripts are data.
3. **The inline fast-path matters.** Alerts are seconds-to-minutes; a guard block should steer in milliseconds.
4. **Label price math.** List-price × recorded tokens is useful; pretending it’s the invoice is not.
5. **Measure honestly.** Ship a readiness doc with a hard cap instead of a feature list that implies done.

### Run it

```bash
git clone https://github.com/chiruu12/arcnet && cd arcnet
cp .env.example .env    # OPENAI_API_KEY for live replay / HQ Agent
uv sync --all-packages && cd hq && pnpm install && cd ..
./scripts/run-demo.sh
# HQ  http://localhost:5173
# API http://127.0.0.1:8000/api/fleet
```

Cold clone renders Time Machine history and Case Files without a key. Optional SigNoz:

```bash
cd deploy && foundryctl cast -f casting.yaml && cd ..
# create service-account key → SIGNOZ_API_KEY → python deploy/provision/setup.py
```

Offline self-check: `scripts/e2e_product_coherence.py`. Live walkthrough script: [`docs/06-demo-script.md`](06-demo-script.md).

### CTA

If you run agents in production — or you’re about to change the model behind one — clone the repo, open `#time_machine` on the Worms session, then `#hq_agent` and read the 2026-07e catalog line out loud: *list-price estimate*. Star the repo, file an issue with a session you’d want to replay, or wire the agent-view twin into the coding agent you already use.

---

## Short-form closing paragraph *(for ~1k posts)*

ArcNet watches agent fleets on SigNoz, defends the trust boundary with Unplug, and closes the loop the industry usually leaves open: hand the incident to a coding agent as structured context (JSON or TOON), then replay the whole recorded session against a candidate model before you ship the swap. Catalog 2026-07e adds current highlights — Kimi, Qwen, DeepSeek — as evidence-grounded list-price projections, not invoice fiction. Griffin is MAD today. Apply is human-gated. The demo is one command away.

---

## Pull-quotes (optional callouts)

- “LangSmith replays a call. ArcNet replays the incident.”
- “List-price estimates, labeled — not your bill.”
- “Outlier, report; normal, silence.” — Griffin MAD
- “Every view has an agent-readable twin.”
- “Prove the upgrade on your own history.”

---

## SEO / social blurb

**Meta description (~155 chars):** ArcNet adds session-level defense, agent-view TOON twins, and counterfactual replay on SigNoz — prove a model upgrade before you ship it.

**Social post:**

> We don’t need another agent dashboard. We need to prove the next model won’t repeat last week’s incident.
> ArcNet: observe → defend → Case File → Time Machine → human-gated apply.
> Catalog 2026-07e · TOON agent_view · MAD Griffin · SigNoz-optional.
> Demo: `./scripts/run-demo.sh` → http://localhost:5173

---

## Fact checklist before publish

- [ ] Griffin described as **MAD** (not TabFM live)
- [ ] Catalog version **2026-07e** + highlight ids match `model_catalog.py`
- [ ] Prices called **list-price estimates**
- [ ] HQ URL is **localhost:5173**
- [ ] Heroes: Edgar `s_ecfdb55d`, Worms `s_2af44726`, version pin `av_demo_agent_j`
- [ ] Verdicts allowed to be **`mixed`** with cost tradeoffs
- [ ] MCP = **PARTIAL**; HTTP evidence preferred
- [ ] HITL / proposals noted as possibly empty until exercised
- [ ] Apply = confirm + possible **manual AgentOS reload**
- [ ] No internal process / grilling / “AI helped me decide” language
- [ ] Readiness numbers, if any, match `docs/20-honest-progress.md` (don’t invent %)

---

## Optional deep appendix (API crumbs)

```bash
# Catalog export
curl -s 'http://127.0.0.1:8000/api/models/catalog' | head -c 300

# Evidence-grounded intel (JSON)
curl -s 'http://127.0.0.1:8000/api/agents/agent_j/model-intel' | head -c 400

# Same intel as TOON
curl -s 'http://127.0.0.1:8000/api/agents/agent_j/model-intel?format=toon' | head -40

# Case File twin
curl -s 'http://127.0.0.1:8000/api/agent-view/case_files/s_ecfdb55d?format=toon' | head -40
```

Related docs: [`27-model-intelligence.md`](27-model-intelligence.md) · [`18-hq-agent.md`](18-hq-agent.md) · [`10-time-machine.md`](10-time-machine.md) · [`12-data-api.md`](12-data-api.md) · [`14-product-guide.md`](14-product-guide.md).
