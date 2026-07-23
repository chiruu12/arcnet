# Path to 95% — Acceptance test appendix

Companion to [`docs/19-path-to-95.md`](../19-path-to-95.md). Run these before moving an area % upward. Prefer scratch DB (`ARCNET_DB_PATH`).

---

## Global gates (every wave PR)

```bash
PYTHONPATH="sdk:server" uv run python -m unittest discover -s sdk/tests
PYTHONPATH="sdk:server" uv run python -m unittest discover -s server/tests
uv run python scripts/check_import_boundaries.py
cd hq && pnpm build
cd hq && pnpm test
PYTHONPATH="sdk:server" uv run python scripts/e2e_path_to_95.py
```

Honesty pins (manual assert in PR body):

- [ ] No TabFM-live claim in HQ/README user chrome
- [ ] Unplug remains in-process
- [ ] `docs/12` diff is additive only
- [ ] Exploration path cannot apply-model without human `confirm`
- [ ] Import boundary green

---

## Area 1 — Positioning

- [ ] HQ chrome: no `demo` badge; empty hints are operator bring-up
- [ ] README leads with enhancement loop; Limitations names MAD + MCP PARTIAL
- [ ] `docs/06` header: hackathon narration ≠ product framing

## Area 2 / WS1 — Cascade

```text
Manual matrix (HQ :5173):
1. #case_files — pick agent_j → versions load
2. pick version → model locked/defaulted to version.model; sessions filter
3. change agent → version, model, session cleared
4. change version → session cleared
5. heroes s_ecfdb55d / s_2af44726 preferred when in filtered set
6. reload hash preserves agent, version, model, session
7. Repeat 1–6 on #time_machine (transcript filter)
8. #hq_agent diagnose uses same cascade before apply
```

- [ ] FE unit tests for cascade reducer (post-WS9)
- [ ] Deep-link without version still works (compat)

## Area 3 / WS2 — Human APIs

```bash
# pagination under filters (extend existing test_product_rework_api)
curl -sD- 'http://127.0.0.1:8000/api/sessions?agent_id=agent_j&limit=2&offset=0' | grep -i X-Total-Count
# write secret
# ARCNET_WRITE_SECRET=test → POST /api/signal without header → 401/403
# empty secret → 2xx + boot log localhost-trust
```

- [ ] All list routes in `12` emit totals under filters
- [ ] Webhook secret reject path covered

## Area 4 — Agent APIs

- [ ] Every `GET /api/agent-view/*` returns envelope keys
- [ ] Session/check/signals/sources/dashboards/incident/replay: no full `recorded_output` in body
- [ ] Tool/SDK timeout returns structured error (post-WS3)

## Area 5 / WS3 — HQ Agent loop

```text
1. propose_model_change → signal source=hq_agent with evidence_refs
2. apply-model without confirm → 400
3. apply-model confirm + session_id → version row + pin
4. check/{session} → version_pinpoint populated
5. response/UI shows agentos_reload_required
6. tool with killed server → error envelope, no hang (>timeout)
```

## Area 6 / WS4 — Version pinpoint

- [ ] Seeded agents have ≥1 version
- [ ] Timeline newest-first
- [ ] Pin mismatch ownership → 4xx
- [ ] Check narrative includes source_ref when set

## Area 7 / WS5 — Model explore

```bash
# with OPENAI_API_KEY and mocked failure injection in unit test:
# recommend_models returns recommendations + degraded/fallback flags
```

- [ ] Live 500/timeout → snapshot fallback (never raise)
- [ ] `compare_replay_verdicts` on hero session cites replay ids
- [ ] Explore MCP/skills cannot apply-model

## Area 8 / WS6 — Griffin

- [x] Status labels estimator `MAD` (or `tabpfn` only if token path active)
- [x] Without seed: no crash; warming/empty honest (Phase 3 cold soak)
- [ ] Evaluate → signal `source=griffin`
- [ ] HQ MAD strip visible on fleet_health

## Area 9 / WS7 — SigNoz

- [x] Status `dashboards` map has distinct UUIDs when provisioned
- [ ] HQ three cards → three URLs
- [ ] Without key: honest false flags
- [x] Evidence helper bounded (post-WS7)
- [x] MCP hang documented; fallback path named in Case File hints

## Area 10 / WS8 — Unplug matrix

| Agent / surface | input | retrieved | tool_call | output | Notes |
|---|---|---|---|---|---|
| Agent J | ✓ | ✓ fetch_url | ✓ | ✓ | S1/S2/S5 |
| Fleet clones L/O | ✓ | ✓ | ✓ | ✓ | same hooks |
| HQ Agent | ✓ | n/a or limited | ✓ tools | ✓ | excerpts only |
| Replay harness | ✓ | ✓ | ✓ | ✓ | live guard |
| model_explore MCP | — | — | — | — | no agent context; JSON only |
| SigNoz MCP (external) | — | — | — | — | not ArcNet process |

- [ ] Matrix filled; gaps closed or explicitly deferred
- [ ] S1/S2/S5 green

## Area 11 / WS9 — E2E

```bash
PYTHONPATH="sdk:server" uv run python scripts/e2e_path_to_95.py
# expect: seed → versions → sessions filter → case-file zip → propose → apply → pin → check pinpoint
cd hq && pnpm test
```

- [ ] CI jobs: python, boundary, hq build, hq test, e2e

## Area 12 / WS11 — Track only

- [ ] Screenshots slots filled OR explicitly cut
- [ ] Video OR cut
- [ ] Slack / form OR cut
- [ ] **Not** averaged into overall %

---

## Wave exit mini-gates

| Wave | Mini-gate |
|---|---|
| A | Catalog fallback merged; version cascade usable in CF+TM; write secret optional path tested; Unplug matrix drafted |
| B | propose→apply→pin→check manual happy path; MAD strip; UUID dashboards; FE residual twins |
| C | e2e + FE tests in CI; scorecard updated with measured %; WS12 deferred list explicit |

---

## Inflating % — forbidden examples

- Adding a checkbox to `17` without exit criteria
- Renaming UI copy only
- Claiming AgentOS model changed when only SQLite `agents.model` updated
- Averaging WS11 into product overall
- Counting TabPFN “ready” without token + latency proof
