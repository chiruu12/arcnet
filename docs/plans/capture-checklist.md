# Recording capture checklist (Run 3 rehearsal — 2026-07-23)

Everything below was verified live on the cold-laptop path except where marked **BLOCKED**.
Companion: [`../06-demo-script.md`](../06-demo-script.md) (beats + narration), [`../24-ship-week-plan.md`](../24-ship-week-plan.md) (run plan).

## Rehearsal results

| Check | Result |
|---|---|
| Cold bring-up, fresh DB (`./scripts/run-demo.sh`, README verbatim) | **PASS** — seed → server + AgentOS + HQ healthy |
| `scripts/e2e_path_to_95.py` (propose→apply→pin + reload flag) | **PASS** |
| `scripts/live_ops_dry_run.py` | **PASS** (AgentOS probe reachable, filters + totals asserted) |
| Hero replay re-verify (`phase4_g4_check.py`) | **BLOCKED — OpenAI key over quota** (see below) |
| Live S1/S2/S5 scenario re-runs (matrix DEFER close-out) | **BLOCKED — same quota** |

Recorded evidence stands meanwhile: `docs/_phase4_g4.json` (both heroes stable `mixed` 3/3).

## Blocker (human)

`POST /api/replay` → replay runtime raises `You exceeded your current quota` (OpenAI billing).
**Top up the OpenAI key before recording** — Beat 5's live `replay.run()` and any hero
re-verification need it. After top-up, re-run:

```bash
uv run python scripts/phase4_g4_check.py --s1 s_ecfdb55d --s4 s_2af44726
PYTHONPATH=sdk:agents uv run python agents/scenarios/runner.py --scenario S1   # then S2, S5
```

## Bring-up for recording

```bash
./scripts/run-demo.sh        # default data/arcnet.db — this is the DB with the hero recordings
```

- **Use the default DB.** A custom `ARCNET_DB_PATH` seeds background fleet only (2 agents,
  18 sessions) — no hero incidents to show.
- **HQ binds `http://localhost:5173`** — use `localhost`, not `127.0.0.1`, in the browser.
- Server `http://127.0.0.1:8000` · AgentOS `http://127.0.0.1:7777`.
- Hero session ids: Edgar **`s_ecfdb55d`** (S1) · Worms **`s_2af44726`** (S4).
- Narration numbers come from `docs/_phase4_g4.json` — read them off the file, don't improvise.

## Screenshot slots (README + `14` §10)

| # | Slot | URL / state | Needs |
|---|---|---|---|
| 1 | Fleet Health | `http://localhost:5173/#fleet_health` — trust posture, `[FORWARD]` flag, Griffin **MAD** strip | stack only |
| 2 | Time Machine | `#time_machine` → cascade to `agent_j` → session `s_ecfdb55d` — baseline attempts exfil (blocked) vs candidate resists, verdict terminal | stack; history renders without key — **live `replay.run()` needs funded key** |
| 3 | SigNoz boards | Fleet / Threats & Trust / Cost / Agno dashboards, ClickHouse SQL panel visible on Threats | Docker: `cd deploy && foundryctl cast -f casting.yaml` → UI `:8080`; `SIGNOZ_API_KEY` in `.env`; `python deploy/provision/setup.py` |
| 4 | Seasonal + Griffin | SigNoz → Alerts → seasonal anomaly rule, next to HQ `#fleet_health` MAD card | Docker + stack |

Operator-flow shots (optional, from the dry-run):

- `#signals` — "showing 40 of N" with N > 40
- `#hq_agent` — apply banner showing `agentos_reload_required`
- After AgentOS restart with `ARCNET_MODEL=gpt-4o` — probe `models_match=true`
- Case Files — version filter showing session totals under `agent_version`

## Known-avoids on camera

- Don't open HQ via `127.0.0.1` (blank — Vite binds `localhost`).
- Beat 4: SigNoz MCP stdio may hang — use the HTTP Query Range / Case File evidence path
  (`docs/06` limitations block); MCP is drama, not the dependency.
- Temp-0 replay is variance reduction, not determinism — narrate only numbers a run actually
  produced.
- Rehearse the full take the day before; deadline day is ship/submit only.
