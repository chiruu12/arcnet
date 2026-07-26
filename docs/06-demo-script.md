# ArcNet — Live demo script (8–12 min)

> **Narration ≠ product framing.** This is the operator walkthrough for a live stack.
> Product limitations (Griffin = MAD, SigNoz MCP PARTIAL, list-price estimates, HITL SQLite)
> live in README + `14-product-guide.md` — do not overclaim what the build does not ship.
>
> Companion publish draft: [`35-blog-script.md`](35-blog-script.md). Older <3:00 camera cut:
> `docs/plans/video-script.md`.

**Thesis:** agents that watch themselves and get better — observe → defend → hand off → prove → improve.

**Stack (required):**

| Port | Service | URL |
|---|---|---|
| **5173** | HQ (Vite) | `http://localhost:5173` — **not** `127.0.0.1` (Vite HMR) |
| **8000** | ArcNet server | `http://127.0.0.1:8000` |
| **7777** | AgentOS / agents | used by `replay.run()` |

```bash
cp .env.example .env          # OPENAI_API_KEY for live replay / HQ Agent
uv sync --all-packages && cd hq && pnpm install && cd ..
./scripts/run-demo.sh
```

Seed pins Agent J hero sessions to `av_demo_agent_j`, registers `demo.luna` (`av_demo_luna_j` / `gpt-5.6-luna`), and loads heroes Edgar `s_ecfdb55d` + Worms `s_2af44726`. **HITL inbox and proposal cards are often empty until you run scenarios / HQ Agent** — treat those as optional beats.

---

## Timing map

| Clock | Beat | Route |
|---|---|---|
| 0:00–0:45 | Cold open + home | `#home` |
| 0:45–2:00 | Fleet health | `#fleet_health` |
| 2:00–3:30 | Threats / signals / sources *(optional live S1)* | `#signals` · `#sources_trust` |
| 3:30–5:30 | Time Machine (Worms → Edgar) | `#time_machine?agent=agent_j&version=av_demo_agent_j&session=s_2af44726` |
| 5:30–7:00 | Case File + agent_view | `#case_files?agent=agent_j&session=s_ecfdb55d` |
| 7:00–9:30 | HQ Agent · catalog 2026-07e · TOON | `#hq_agent?agent=agent_j` |
| 9:30–11:00 | Apply flow *(optional)* + honesty close | same |
| +2–4 min | Deep dive: Griffin / SigNoz / live scenario | `#dashboards` · SigNoz `:8080` |

Target **~10 minutes** core; skip optional rows if the clock is tight.

---

## Preflight (2 min before audience)

1. Breadcrumb shows `· live` (not `api_down`).
2. Sidebar mini-fleet lists `agent_j` / `agent_l` / `agent_o` (and `agent_opus` if seeded).
3. Quick API sanity:
   ```bash
   curl -s http://127.0.0.1:8000/api/fleet | head -c 200
   curl -s 'http://127.0.0.1:8000/api/agents/agent_j/model-intel' | head -c 200
   # optional TOON twin:
   curl -s 'http://127.0.0.1:8000/api/agents/agent_j/model-intel?format=toon' | head -20
   ```
4. Open HQ at **`http://localhost:5173`**.
5. Decide optional beats:
   - **Proposals empty?** Skip apply demo; show recommendation buckets + “new in catalog” instead.
   - **HITL empty?** Skip or say “empty until a pending request is posted.”
   - **SigNoz up?** Only if Docker + `SIGNOZ_API_KEY` provisioned — otherwise stay SQLite-primary.

---

## Cold open (0:00–0:45) — `#home`

Open `http://localhost:5173/#home`.

> "ArcNet is the maintenance layer for agent fleets. Agents and their harnesses need maintenance like any other software — ArcNet watches behavior, cost, and the trust of everything an agent ingests, then closes the loop: defend in real time, hand the incident to a coding agent, and prove a model upgrade on your own recorded sessions."

Point at the loop strip + live stat tiles (fleet / sessions / threats / signals / replays). Honesty strip stays visible — leave it.

---

## Beat 1 — Observe the fleet (0:45–2:00) — `#fleet_health`

Navigate `// observe` → `fleet_health`, or `#fleet_health`.

Show Agent J **`[FORWARD]`** (forward-facing / higher injection risk), sessions/threats/blocked/cost, Griffin **MAD** strip (say the word MAD — not TabFM).

> "These are AI agents. The ones that face the outside world can be turned against you. ArcNet watches all of them — behavior, cost, and trust posture. Griffin is a MAD statistical baseline today: outlier, report; normal, silence."

Optional one-liner: background agents L/O exist so the fleet reads as a fleet, not a single hero.

---

## Beat 2 — Defend / signals (2:00–3:30)

### Path A — Seeded history (safe default)

`#signals` then `#sources_trust`.

> "Signals are steer, pause, kill, note — the control plane for live agents. Sources trust is the ledger of what Unplug scanned: origin, trust level, scan action."

If HITL has rows: `#hitl` → approve/reject once. If empty:

> "HITL is empty until something posts a pending request — SQLite bookkeeping today, not a full AgentOS pause relay."

### Path B — Live S1 (optional, needs key + agents up)

```bash
PYTHONPATH=sdk:agents uv run python agents/scenarios/runner.py --scenario S1
```

Watch `#signals` for a new steer/block row; `#sources_trust` for the untrusted scrape. Flip briefly to SigNoz if live (`#dashboards` → Threats & Trust).

> "The attack came through an untrusted source. Unplug filters before the model; the exfil tool call is blocked; a steer signal lands on the inline fast-path in milliseconds — SigNoz alert is the system of record behind it."

---

## Beat 3 — Time Machine (3:30–5:30) — the whoa

Deep-link:

```
http://localhost:5173/#time_machine?agent=agent_j&version=av_demo_agent_j&session=s_2af44726
```

Cascade should resolve **agent_j → av_demo_agent_j → legacy-baseline-v1 → Worms**. Show stored verdict first (cold clone works offline).

> "Here's the part nobody else does at the session level. LangSmith and Braintrust replay a call — this replays the whole incident: same goal, same tools, same trust checks, only the brain changes."

Narrate **Worms** numbers from the screen (never invent): baseline killed / looped vs candidate stops earlier — verdict is often `mixed` with a cost tradeoff. Honesty: security/reliability wins can cost more.

Then switch session to Edgar:

```
#time_machine?agent=agent_j&version=av_demo_agent_j&session=s_ecfdb55d
```

> "Edgar: the shield contained the exfil at runtime — but the baseline still followed the injection. The candidate resists. Prove the upgrade on incidents your fleet actually recorded."

**Optional live `replay.run()`** (needs `OPENAI_API_KEY` + AgentOS `:7777`, ~30–90s): click once, narrate progress over SSE, read the majority-of-3 verdict. Temp 0 is variance reduction, not determinism — say the numbers the run produced.

---

## Beat 4 — Case File + agent_view (5:30–7:00)

```
http://localhost:5173/#case_files?agent=agent_j&version=av_demo_agent_j&session=s_ecfdb55d
```

Show root cause, recommended actions, SigNoz evidence pointer / MCP hint. Click **`export_case_file()`** or **`hand_to(claude_code)`** so the zip download is visible.

Toggle top-bar **`human_view | agent_view`**.

> "Every view has a machine-optimal twin. Your coding agent doesn't read a screenshot — it reads a bounded envelope with links across session → threats → models → case file."

Optional curl proof:

```bash
curl -s http://127.0.0.1:8000/api/agent-view/case_files/s_ecfdb55d | head -c 400
curl -s 'http://127.0.0.1:8000/api/agent-view/case_files/s_ecfdb55d?format=toon' | head -30
```

---

## Beat 5 — HQ Agent · catalog 2026-07e · TOON (7:00–9:30)

```
http://localhost:5173/#hq_agent?agent=agent_j
```

Stay in **human_view** first.

1. Diagnose strip: agent → version (`av_demo_agent_j` / `av_demo_luna_j`) → optional session pin.
2. Status line: `catalog=2026-07e` · **list-price estimate** · usage token totals from recorded sessions.
3. **`// new in catalog`** — call out highlights by id:
   - `kimi-k2.7-code`, `kimi-k3`
   - `qwen3.8-max-preview`, `qwen3.6-35b-a3b`
   - `deepseek-v4-flash`, `deepseek-v4-pro`
4. Scroll **recommendation buckets**: `recommended_upgrade` · `cost_saver` · `peer` · `not_advised` — fit reasons cite recorded evidence; Δ cost is same tokens × different list price.
5. Flip to **`agent_view`**: panels `model_intel.toon` / `model_proposals.toon`.

> "Catalog 2026-07e is a dated static catalog — dollars are list-price estimates, not your bill. Projections reuse this agent's recorded token totals. Agent view encodes the same intel as TOON — tabular, token-efficient for machine consumers. You can also fetch `?format=toon` on the API."

If proposal cards exist: select one → `select_for_apply()` → fill model/version → check **confirm** → apply. Say the reload banner out loud: SQLite updated; **AgentOS reload is manual**.

If proposals empty:

> "Proposal inbox is empty until HQ Agent runs — for example: `PYTHONPATH=sdk:agents uv run python -m hq_agent \"fleet health + griffin MAD + proposals\"`. The buckets and catalog highlights are already enough to show the improve path."

Do **not** claim auto-remediation or silent production swaps.

---

## Close (9:30–11:00)

Return `#home` or `#fleet_health`. Wordmark `> arcnet`.

> "Observe, defend, hand off, prove, improve. ArcNet — your agents, watching themselves, and getting better."

---

## Optional deep dive (+2–4 min)

| Topic | What to show | Honesty line |
|---|---|---|
| **Griffin** | Fleet MAD strip · `GET /api/griffin/status` | MAD live; TabFM Phase 7 / not on camera |
| **SigNoz** | `#dashboards` → UI `:8080` · OpenInference waterfall | Optional Docker path; SQLite-primary demo works without it |
| **Live Worms** | `runner.py --scenario S4` | Token spike → Griffin / kill choreography |
| **Corpus** | `POST /api/replay/corpus` stored mode | Aggregate stored verdicts — offline, no AgentOS |
| **Write auth** | mention only if asked | localhost demo writes open unless `ARCNET_WRITE_SECRET` set |

---

## Hash route cheat sheet

```
#home
#fleet_health
#signals
#hitl
#sources_trust
#time_machine?agent=agent_j&version=av_demo_agent_j&session=s_2af44726
#time_machine?agent=agent_j&version=av_demo_agent_j&session=s_ecfdb55d
#case_files?agent=agent_j&version=av_demo_agent_j&session=s_ecfdb55d
#hq_agent?agent=agent_j
#dashboards
```

Toggle: top bar `human_view | agent_view` (TOON panels on `hq_agent` in agent mode).

---

## Talking points — say / don't say

| Say | Don't say |
|---|---|
| Griffin = **MAD** statistical baseline | "TabFM / TabPFN is live" |
| Catalog dollars = **list-price estimates** as of **2026-07e** | "This is your invoice / measured spend" |
| Time Machine replays the **whole session** | "We're a LangSmith clone" |
| Agent-view + optional `?format=toon` | "Agents scrape the UI" |
| Apply is **human-gated**; AgentOS restart is **manual** | "We hot-swap production models automatically" |
| HITL / proposals may be empty until exercised | Fake a full inbox |
| SigNoz MCP = **PARTIAL**; HTTP evidence is the product path | "MCP stdio is rock solid" |
| Hero verdicts are often **`mixed`** with cost tradeoffs | Invent green "improved everywhere" scores |

---

## Backup / failure modes

| Failure | Recovery |
|---|---|
| `api_down` | Restart `./scripts/run-demo.sh`; confirm `:8000` |
| HQ blank / HMR weird | Use `localhost:5173`, not `127.0.0.1` |
| Replay hangs | Skip live run; use stored Worms/Edgar verdicts |
| No OPENAI key | Entire observe + stored Time Machine + catalog + TOON still demoable |
| Empty proposals / HITL | Narrate optional; stay on catalog buckets + heroes |
| SigNoz down | Stay on SQLite-primary; skip `#dashboards` deep dive |

---

## Judge / audience checklist

- [ ] `./scripts/run-demo.sh` → HQ live on `localhost:5173`
- [ ] Fleet shows forward-facing Agent J + MAD strip
- [ ] Time Machine opens Worms + Edgar via hash routes (`av_demo_agent_j`)
- [ ] Case File export downloads
- [ ] `#hq_agent` shows catalog **2026-07e**, **new in catalog** highlights, recommendation buckets
- [ ] `agent_view` shows TOON panels (or curl `?format=toon`)
- [ ] Said out loud: list-price estimates · MAD · human-gated apply
- [ ] Optional: one live scenario or one live replay — not both if time-boxed
