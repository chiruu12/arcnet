# ArcNet submission video, no-live-demo version

Target **under 3:00**. Nothing is executed on camera. You capture every screen ahead of time
as short clips or stills, then assemble and record voice-over on top. If a capture looks wrong,
you recapture it instead of discovering it mid-take.

Replaces `video-script.md` for the actual recording. That file stays as the live-run reference.

**The form grades four things.** About the project, tech stack and architecture, demo,
learning and growth (optional). Segment 2 exists only to satisfy the architecture line. Do not
cut it. If you run long, cut Segment 7.

---

## Phase A: capture everything first (no narration yet)

Bring the stack up, then record these as separate silent clips. Aim for 10 to 20 seconds each so
you have room to trim. Move the cursor slowly. Nothing needs to be typed on camera.

| # | Capture | Notes |
|---|---|---|
| C1 | HQ `#home` | Slow drift across the loop strip |
| C2 | The mermaid architecture diagram on GitHub | `docs/02-architecture.md`, let it fill frame |
| C3 | `deploy/casting.yaml` on GitHub | 7 lines, 2 seconds is enough |
| C4 | SigNoz trace waterfall | `agent_j.run` expanded, attributes panel open |
| C5 | SigNoz Threats and Trust dashboard | Include the ClickHouse SQL panel |
| C6 | HQ `#fleet_health` | Fleet cards, `[FORWARD]` tag, Griffin MAD strip |
| C7 | HQ `#signals` with the Edgar threat rows | Scroll slowly through the verdicts |
| C8 | Case file view, then the `human_view / agent_view` toggle flip | The toggle flip is the moment |
| C9 | Time Machine on Edgar `s_ecfdb55d`, verdict visible | **The single most important capture** |
| C10 | Time Machine on Worms `s_2af44726`, stored verdict strip | Optional, only if time allows |
| C11 | HQ `#hq_agent` model intel | `catalog=2026-07e` line visible |

Capture C4 and C5 in the same sitting as everything else. Hero traces age out of ClickHouse, so
an old trace may simply not be there.

---

## Phase B: the seven segments

Fill in your own wording. What matters per segment is the point being made and the time budget.

### Segment 1, about the project (0:00 to 0:15)
**On screen:** C1

**Cover:** what ArcNet is in one sentence, and the problem it exists for. Agents browse, read
tickets, touch databases, and they rot like any other software. Nobody ships you the maintenance
loop for that. ArcNet is that loop, built on SigNoz.

**Land this:** watch the fleet, defend it, prove the fix on your own recorded history.

---

### Segment 2, tech stack and architecture (0:15 to 0:40)
**On screen:** C2, then C3 for the last 3 seconds

**This is a graded line item.** Say the component names out loud, clearly. Judges are listening
for them, and a demo-only video cannot show this.

**Cover, in this order:**
- Agents run on **Agno**
- An in-process **SDK** does two jobs: OpenTelemetry instrumentation via
  **openinference-instrumentation-agno**, and guardrails via **unplug-ai**
- Traces go to **self-hosted SigNoz** over **OTLP**, **ClickHouse** underneath
- A **FastAPI** server reads back through the **Query Range API**, runs Griffin and the Time Machine
- **React** UI on top
- SigNoz itself is installed with **Foundry** from one declarative file, and the committed lock
  file reproduces the stack exactly

**Trace the arrows with your cursor while you talk.** Follow the loop: SDK to OTLP to SigNoz to
alert webhook to server to SSE and back into the agent.

---

### Segment 3, observe (0:40 to 1:05)
**On screen:** C4, then C6

**Cover:** every model call, tool call, token and dollar lands in SigNoz. Point at the span
shape on screen, `{agent}.run` to `{model}.invoke` to `{tool}`. Mention that every source the
agent ingests carries a trust level.

Then Griffin on the fleet view: a MAD statistical baseline per metric, which flags a runaway
agent from minute one. Contrast it with SigNoz's seasonal anomaly rule, which needs history.
Griffin covers the cold start, the SigNoz rule confirms once there is history.

**Honesty:** Griffin is MAD. Never say TabFM.

---

### Segment 4, defend (1:05 to 1:35)
**On screen:** C7, then C5

**Cover the mechanism, not just the outcome.** A scraped page carries a hidden instruction. The
page itself scans clean, so the agent is allowed to read it. What gets blocked is the
consequence: the moment that tainted content tries to become a `send_email` call, it is stopped
at the trust boundary and a steer signal reaches the running agent in milliseconds.

Then say why that is recorded well: the verdict on screen carries rule, pattern class, and risk
score as structured span attributes, so it is something you can chart and alert on rather than a
boolean.

**Do not narrate `injection` or `ignore_previous` here.** The poisoned page scans allow at the
retrieved checkpoint. The threats that actually fire are `retrieved_source_in_side_effect` at
0.85 and `crescendo_block` at 0.92. Blocking at the side effect is the stronger story anyway,
because it shows taint tracking is the load-bearing defense.

---

### Segment 5, hand off (1:35 to 2:00)
**On screen:** C8

**Cover:** the thing that fixes your agent harness these days is another agent. So every view has
a machine-readable twin, cross-linked, so a coding agent can walk the incident graph without
guessing URLs. Show the toggle flip. Mention JSON or token-efficient TOON. The case file exports
with a fix prompt and trace evidence attached.

---

### Segment 6, prove (2:00 to 2:35)
**On screen:** C9, then C10 if you have room

**This is your differentiator. Give it the most time.**

**Cover:** this replays a whole recorded incident against a different model. Same goal, same tool
outputs, same guardrails, only the model changes. Three runs, majority verdict.

**Read the numbers that are actually on your screen.** Do not improvise them. The stored verdicts
changed once when the fixture was regenerated, so trust the capture, not memory.

**Say the unflattering half out loud.** On the injection incident the candidate resists in all
three replays and costs several times more than the baseline. That is a `mixed` verdict, not a
clean win, and the tool says so. A tool that only ever says upgrade is one you stop believing.
This is also your strongest "learning and growth" moment if you want to claim that optional line.

**Land this:** your trace history becomes a behavioral regression suite for the harness.

---

### Segment 7, improve and close (2:35 to 2:58)
**On screen:** C11, then back to C1 for the final 5 seconds

**Cut this segment first if you are over time.**

**Cover:** upgrade recommendations from a dated catalog, costs projected from this agent's own
recorded tokens, labeled as list-price estimates rather than an invoice. The agent proposes, a
human confirms, nothing hot-swaps production silently.

**Close on:** observe, defend, hand off, prove, improve. Built on SigNoz.

---

## Rules for the voice-over

- **Only say numbers that are visible in the capture.** If you cannot see it on screen, cut it.
- **Griffin is MAD**, not TabFM.
- **SigNoz MCP stdio is partial.** The HTTP handoff is the product path. Only mention MCP if you
  have time to add the caveat.
- **Catalog dollars are list-price estimates.**
- **Verdicts are allowed to be `mixed`.** That is a feature, so say it like one.
- Readiness is roughly 64 percent if anyone asks. Do not round up.

## Before you upload

- [ ] Total runtime under 3:00
- [ ] Segment 2 present and the stack names are audible
- [ ] Every number spoken appears on screen
- [ ] **AI assistant use declared.** The rules say undeclared use is a disqualification. Put a
      line in the video description, for example: "AI coding assistants were used during
      development and are disclosed per hackathon rules."
- [ ] Uploaded unlisted, then opened in a private window to confirm it plays logged out
