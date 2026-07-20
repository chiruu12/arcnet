# Build log

## Day 0 — Mon Jul 20 (planning)
- Docs 00–07 + README + HQ mock (`docs/mock/hq.html`) written; scope locked.
- Framework: **Agno** (AgentOS) instrumented via `openinference-instrumentation-agno`; Unplug as `UnplugGuardrail`.
- SigNoz AI surface folded in: MCP server (Case File beat + dev-time), agent-skills, native seasonal anomaly alert. Noz = Cloud-only, out.
- Added **Griffin** (F13): TabFM zero-shot anomaly detection + conformal bands; report-only-outliers.
- Full review pass applied. Fixes: corrected calendar (Jul 20 = **Mon**, deadline **Sun Jul 26**); re-tiered so the demo rides on P0 not P1; rebalanced overloaded Phase 4; moved TabFM spike to Day 0 and seed.py to Phase 3; added S4 "Griffin-first" choreography; pinned signal schema; enumerated env surface; added cost price source; reconciled HQ↔SigNoz claim.
- Deps verified installable: unplug-ai 0.5.2, agno 2.7.4, openinference-instrumentation-agno 0.1.38, tabpfn 8.1.0, signoz-mcp-server v0.8.0; TabFM repo + HF weights confirmed live.
- **Next (Phase 0 checklist in 03-plan.md):** SigNoz up, Agno hello trace, unplug smoke, TabFM latency spike, service key + Query/metrics-list call, submission form + deadline time.
