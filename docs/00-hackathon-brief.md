# Hackathon Brief — Agents of SigNoz

Source: https://www.wemakedevs.org/hackathons/signoz (fetched 2026-07-20)

## Facts

- **Event**: Agents of SigNoz — WeMakeDevs × SigNoz
- **Dates**: **July 20–26, 2026** — Mon Jul 20 through **Sun Jul 26** (verified weekdays). Event runs through the 26th, so treat **Sun Jul 26 as the deadline**; exact submission time is TBD from the form (confirm in Phase 0).
- **Prize pool**: $20,000 total
- **Our track**: **Track 01 — AI & Agent Observability** ("Trace, monitor, and debug AI-native systems")
- **Track 1 prize**: MacBook Air per team member (cash equivalent available)
- **Team**: solo (max 4 allowed; every member gets full prize)
- **Submission form**: "coming soon" on the page — check the page / SigNoz Slack daily for the form + exact deadline time

## Rules that constrain us

1. **Must use or integrate with SigNoz.** Non-negotiable; also a judging category.
2. **No reuse of existing projects or prior work.** Everything in the ArcNet repo is written fresh during the event. Unplug is consumed strictly as a published PyPI dependency (`unplug-ai==0.5.2`) — the same way we consume Agno or FastAPI. We do not copy Unplug code into this repo, and we don't present Unplug itself as the hackathon build; ArcNet (platform, SDK, server, dashboard, scenarios) is the build. **The honest wrinkle: unplug-ai is our own library.** Defense-in-depth for that: (a) the disclosure sits at the top of the public README, not buried here; (b) Phase 0 posts the same framing in the SigNoz Slack and asks the organizers for an explicit ruling in writing — a proactive ask beats a post-hoc defense; record the answer: ____
3. **AI assistants allowed** (explicitly permitted).
4. Tech stack open-ended.

## Judging criteria → how ArcNet scores each

| Criterion | Our answer |
|---|---|
| Potential Impact | The field admits nobody closes the trace→fix→proof loop (LangSmith/Langfuse/Arize). ArcNet does: observe → defend → hand to the coding agent → **prove a fix is better**. Source-trust + forward-facing risk targets the #1 agent risk (OWASP LLM01 injection). |
| Creativity & Innovation | **The Time Machine** — counterfactual replay of a real incident against a different model, proof not vibes. The **agent-view** — every datum has a machine-optimal twin coding agents consume. Self-correcting agents via signals. (Differentiated, not unprecedented — name the prior art ourselves: LangSmith/Braintrust replay at the *call/dataset* level, Sentry Seer exports one structured root-cause blob; ArcNet replays the **whole agent session** with trust checks live, and gives **every panel** a machine twin. See `08-vision-v2.md`.) |
| Technical Excellence | OpenInference/OTel semantic conventions (the real keys the instrumentor emits), clean SDK layering, idiomatic Agno guardrails/HITL, typed FastAPI, provisioned-as-code dashboards/alerts. |
| **Best Use of SigNoz** | All three OTel signals (traces, metrics, logs) surfaced through SigNoz dashboards + alert rules (incl. native seasonal anomaly) + webhook channel + Query Range API powering our own UI + ClickHouse panels + **SigNoz MCP server** (dev-time and in the demo) + **SigNoz agent skills** in our workflow + prebuilt Agno dashboard template. See `04-signoz-integration.md` checklist. |
| User Experience | Product-grade UI in the Unplug design language (dark terminal, cyan, mono), the `human ⇄ agent view` toggle, the Time Machine side-by-side replay, one-command demo. |
| Presentation Quality | Scripted demo (`06-demo-script.md`), tight README, architecture diagram, <3min video. |

## Side quests (optional, decide later)

- **Social track**: post tagged @wemakedevs + SigNoz → swag. Cheap to do on demo day.
- **Blog competition** deadline was Jul 19 (missed — ignore).

## Support

- SigNoz Slack community for real-time help (join in Phase 0 — also where submission info lands).
- SigNoz docs: self-host install, **Agno monitoring guide** (https://signoz.io/docs/agno-monitoring/), Query Range API, webhook channel, AI/MCP-server + agent-skills.
