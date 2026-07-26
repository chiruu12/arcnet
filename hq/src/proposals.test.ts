/**
 * Node assert tests for proposal parsing + TOON encoding.
 * Run: node --experimental-strip-types --test src/proposals.test.ts src/toon.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { parseModelProposal } from "./proposals.ts";
import { modelIntelToToon, proposalsToToon } from "./toon.ts";
import type { SignalRow } from "./types.ts";

describe("parseModelProposal", () => {
  it("extracts from/to models and evidence refs from guidance", () => {
    const row: SignalRow = {
      signal_id: "sig-1",
      session_id: "sess-1",
      agent_id: "agent_j",
      kind: "note",
      severity: "info",
      reason: "upgrade for reasoning workload",
      guidance:
        "Proposed model change for agent_j: legacy-baseline-v1 → gpt-5.6-terra. task_type=reasoning. evidence_refs=agent:agent_j,replay:abc.",
      source: "hq_agent",
      status: "open",
      created_at: 1,
    };
    const p = parseModelProposal(row);
    assert.equal(p.from_model, "legacy-baseline-v1");
    assert.equal(p.to_model, "gpt-5.6-terra");
    assert.equal(p.task_type, "reasoning");
    assert.deepEqual(p.evidence_refs, ["agent:agent_j", "replay:abc"]);
  });
});

describe("modelIntelToToon", () => {
  it("emits tabular candidates block", () => {
    const out = modelIntelToToon({
      agent_id: "agent_j",
      current_model: "legacy-baseline-v1",
      catalog_version: "2026-07e",
      price_label: "catalog",
      models: [],
      usage_evidence: {
        session_count: 1,
        sessions_with_token_usage: 1,
        input_tokens: 100,
        output_tokens: 50,
        total_tokens: 150,
      },
      workload_evidence: {
        session_count: 1,
        threat_count: 0,
        threat_rate: 0,
        replay_count: 0,
        verdict_counts: {},
        adversarial_replay_count: 0,
      },
      baseline_projected_cost_usd: 0.01,
      candidates: [
        {
          id: "gpt-5.6-terra",
          provider: "openai",
          capability_tier: "frontier",
          cost_class: "premium",
          tier: "frontier",
          status: "current",
          input_usd_per_mtok: 1,
          cached_input_usd_per_mtok: 0.5,
          output_usd_per_mtok: 4,
          context_window: 128000,
          max_output_tokens: 8192,
          reasoning: true,
          strengths: "reasoning",
          caveats: [],
          price_verified: null,
          projected_cost_usd: 0.02,
          projected_cost_usd_cached: 0.015,
          projected_cost_delta: 0.01,
          price_label: "catalog",
          is_current: false,
          bucket: "recommended_upgrade",
        },
      ],
      reasoning_recommendation: null,
      honesty: "",
    });
    assert.match(out, /candidates\[1\]\{id,bucket,tier,cost,in,cached,out,ctx,delta,status,current\}:/);
    assert.match(out, /gpt-5\.6-terra,recommended_upgrade/);
  });
});

describe("proposalsToToon", () => {
  it("encodes proposal rows tabularly", () => {
    const out = proposalsToToon([
      {
        signal_id: "sig-1",
        agent_id: "agent_j",
        session_id: null,
        status: "open",
        created_at: 1,
        reason: "upgrade",
        from_model: "a",
        to_model: "b",
        task_type: null,
        evidence_refs: ["agent:agent_j"],
        guidance: null,
      },
    ]);
    assert.match(out, /proposals\[1\]\{/);
    assert.match(out, /sig-1,open,a,b/);
    assert.match(out, /evidence\[sig-1\]: agent:agent_j/);
  });
});
