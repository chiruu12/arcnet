# ArcNet — Ship-week plan + next-run prompts

**Date:** 2026-07-23 (Thu). **Submission:** Sun Jul 26 (exact time TBD — Track D).
**Base state:** original build phases 0–6 complete; productization Phases 2–4 (docs/21 numbering) done; overall **~57% / ≤60% cap** ([`20-honest-progress.md`](20-honest-progress.md)).
**Open PRs at draft time:** #19 (Phase 4 live-ops), #20 (next-agent packets, stacked on #19's older tip), #21 (product-fit overview, stacked on #20).
**Companions:** [`22-next-agent-packets.md`](22-next-agent-packets.md) (packet specs — authoritative for P5/P6/P7 details), [`21-next-phases-plan.md`](21-next-phases-plan.md) (phase bundles), [`06-demo-script.md`](06-demo-script.md) (recording).

This doc sequences the runs between now and submission, carries the copy-paste prompt for each run, and fences post-hackathon work so nothing burns the remaining window.

---

## Sequence

```
Run 0 (merge train)  →  Run 1 (P5-B honesty)  ∥  Run 2 (P5-A Unplug matrix)  →  Run 3 (demo rehearsal)
                                   │
human track:  Slack ruling + submission form (Thu)  →  screenshots (Fri)  →  video (Sat)  →  submit (Sun, hours of buffer)
```

Gate between runs: **CI green + review findings fixed + merged to main**. Runs 1 and 2 may run in parallel (disjoint files; only the docs/22 tracking table overlaps — trivial conflict, take both rows).

**Fenced until after submission:** P6-A/B/C, P7-A/B, any SigNoz/seed/fixture polish (standing pin), any % re-score above 60.

---

## Run 0 — merge train (sequential, first)

```markdown
You are working in the ArcNet repo. Phase 4 work is done; before any new work, land the open
PRs so main is a clean base. The PRs are STACKED: #20 branched from an older tip of #19's
branch, and #21 branched from #20. Do these in order, verifying between steps:

1. Checkout `phase-4-live-ops`, run the full verification suite:
   - `PYTHONPATH=sdk:server:. uv run python -m unittest discover -s server/tests`
   - `PYTHONPATH=sdk:server uv run python -m unittest discover -s sdk/tests`
   - `PYTHONPATH=sdk:server:. uv run python -m unittest discover -s agents/tests`
   - `uv run python scripts/check_import_boundaries.py`
   - `cd hq && pnpm test && pnpm build`
   All must pass. Fix any outstanding review P1s on PR #19, then merge #19 into main.
2. Rebase `plan/next-agent-packets` onto the new main. Resolve conflicts in docs/20 and
   docs/21 by KEEPING the newer measured numbers already on main (~57% / ≤60% cap). Update
   docs/22's tracking table: Phase 4 = merged via #19. Merge PR #20.
3. Rebase `docs/product-fit-overview` onto main (after #20 its diff should shrink to the
   product-overview doc + honesty-align edits; if the rebase shows #20 was fully contained
   in #21, merging #21 and closing #20 as superseded is acceptable — say so in the PR).
   Review docs/23-product-overview.md and every docs edit against the honesty pins: no
   claims above ~57%/≤60, no "TabFM live", MAD + MCP PARTIAL named in limitations. Merge if
   clean; otherwise leave specific review comments and stop — do not force it.
4. Commit the untracked `docs/24-ship-week-plan.md` (this plan) on main: one commit,
   message `add ship-week plan`. Link it from docs/21's execution-sequence section.
5. Delete merged branches. Confirm CI green on main.

Rules: commits one-line WHAT-shipped; no process narration. Do not start Phase 5/6/7 work
in this run.
```

---

## Run 1 — P5-B: honesty chrome + excerpt caps

```markdown
You are working in the ArcNet repo, branch `phase-5-honesty` off main. Execute packet **P5-B**
from `docs/22-next-agent-packets.md` exactly as specced there. Context: hackathon submission
is Sun Jul 26 — this packet is what makes the README/demo claims survive judge scrutiny.

Goal: stop lying / stop leaking. README + docs/14 + docs/06 Limitations name **MAD + MCP
PARTIAL**; zero user-facing chrome claims "TabFM live" or demo-badges; Case File / signal
excerpts are size-capped; the `full_transcript` escape hatch (A15) is gated or documented +
tested as intentional.

Files: README.md, docs/14-product-guide.md, docs/06-demo-script.md, hq/src/views/* (grep for
chrome), server/arcnet_server/read_models.py, server/tests/, agents/hq_agent/prompt.md,
skills/arcnet-hq-agent/.

Exit criteria (all must pass, verbatim from docs/22):
(a) `rg -n 'TabFM live|demo.badge|demo badge' README.md docs/14-product-guide.md
    docs/06-demo-script.md hq/src` → 0 product claims (honesty "not live" strings OK);
(b) Limitations mention MAD + MCP PARTIAL;
(c) unit tests prove excerpt bounds — no giant dumps on agent-view incident/signals;
(d) `full_transcript` gated (flag/size) or documented + tested as intentional;
(e) hq build + server tests + import boundary green.

Anti-scope: NO new features, NO HITL UI, NO TabFM work, NO SigNoz/seed/fixture polish
(standing pin), NO % changes to docs/20 (overall stays ~57%/≤60). Note: forward-looking
capability claims ("TabFM coming soon") count as chrome — remove them too. Update the
docs/22 tracking row for P5-B in your PR. One-line WHAT-shipped commits; fix review P1s
before merge.
```

---

## Run 2 — P5-A: Unplug coverage matrix + scenario regression (parallel with Run 1)

```markdown
You are working in the ArcNet repo, branch `phase-5-unplug-matrix` off main. Execute packet
**P5-A** from `docs/22-next-agent-packets.md` exactly as specced there.

Goal: complete the product-agent × tool × checkpoint Unplug coverage matrix (WS8); keep
S1/S2/S5 regression green; any gap becomes an explicit DEFER row with a reason — never a
silent hole.

Files: sdk/ Unplug guard paths, agents/scenarios/ (runner.py, S1/S2/S5), agents/tests/, a
matrix table under docs/ or docs/plans/, optional server/tests/ if signals are asserted.

Exit criteria (verbatim from docs/22):
(a) matrix covers 100% of in-scope product agents OR has explicit DEFER rows with reasons;
(b) S1/S2/S5 green — live via `agents/scenarios/runner.py` if OPENAI_API_KEY is present,
    otherwise CI-equivalent unit stubs, and DOCUMENT which path ran;
(c) import boundary still green;
(d) no new auto-remediation behavior.

Anti-scope: TabFM, SigNoz fixture polish, Wave C/HITL UI, % inflation. If docs/22's
tracking table conflicts with the honesty branch, take both rows. One-line WHAT-shipped
commits; fix review P1s before merge.
```

---

## Run 3 — demo rehearsal (H-1's codeable half; after Runs 1–2 merge)

```markdown
You are working in the ArcNet repo, branch `demo-rehearsal` off main. The submission video
and screenshots get captured this weekend — your job is to make sure NOTHING on camera
depends on luck. Verification + small fixes only, not features.

1. Cold bring-up: from a clean DB path (fresh `ARCNET_DB_PATH`), run `./scripts/run-demo.sh`
   exactly as the README quick start says. Every command in the README must work as written —
   fix the README or the script if they drift, whichever is wrong.
2. Hero stability: with OPENAI_API_KEY, run `uv run python scripts/phase4_g4_check.py` —
   both heroes must be stable 3/3 (Edgar exfil 1→0, Worms killed→partial). If either flakes,
   diagnose and fix WITHOUT weakening the guard; re-run 3×.
3. Live-ops beat: run `scripts/live_ops_dry_run.py` and `scripts/e2e_path_to_95.py`; both
   green.
4. Walk every screenshot slot listed in README "Screenshots" + docs/14 §10 against the real
   UI: for each slot, record the exact URL, view, and app state needed in a capture
   checklist appended to docs/06-demo-script.md (or docs/plans/capture-checklist.md — match
   existing patterns). Note which slots need the Docker/SigNoz stack and the exact bring-up
   commands for those.
5. Anything broken you find: fix if small, otherwise record it in the checklist as a
   known-avoid ("don't click X during recording").

Exit: cold bring-up works from README verbatim; heroes 3/3; dry-run + e2e green; capture
checklist exists with per-slot state. Anti-scope: no new features, no % changes, no P6/P7
work, no SigNoz/seed polish beyond what recording strictly needs. One-line commits.
```

---

## Human track (Track D/H — the only hard-dated work)

| When | What |
|---|---|
| **Thu Jul 23** | Find the submission form + exact deadline time. (Slack provenance post: **skipped by choice** — the README-top disclosure + docs/00 remain the compliance stance.) |
| **Fri Jul 24** | Using Run 3's capture checklist: bring up the SigNoz stack, capture the 4 README screenshot slots + extras. Restart AgentOS once after an apply-model for the optional reload screenshot. |
| **Sat Jul 25** | Protected half-day: record the video per docs/06 (six beats, <3:00, honest `mixed` narration). Embed screenshots in README. |
| **Sun Jul 26** | Code freeze except README/media. Submit with hours of buffer, not minutes. |

---

## Post-hackathon queue (fenced — do not start before submission)

Order: **P6-A** (HITL UI) → **P6-B** (shell recover + threats + twins) → **P6-C** (corpus scorecard or defer) → **P7-A** (TabFM spike re-measure; may start parallel with P6) → **P7-B** (TabFM ship + MAD degrade). After P6-B, re-measure docs/20 citing Phase 5–6 exits — the first legitimate chance for the overall number to move past 60.

Per-run prompt template:

```markdown
You are working in the ArcNet repo, branch `<packet-branch>` off main. Read
`docs/22-next-agent-packets.md` and execute packet **<ID>** exactly: its goal, files, exit
criteria, dependencies, and anti-scope are authoritative. Honesty pins apply (~57%/≤60 until
a measured re-score cites exits; no TabFM-live claims before P7-B exits). Update the
packet's tracking row in your PR. One-line WHAT-shipped commits; fix review P1s before
merge.
```

---

## Anti-inflation reminders (copy into PR bodies)

- Overall remains **~57% / ≤60%** until a measured re-score cites Phase exits.
- TabFM research / spike ≠ TabFM shipped.
- Hackathon screenshots ≠ product robustness.
- No SigNoz/seed/fixture polish beyond Phase 3 (standing pin).
- Track H/D never average into overall %.
