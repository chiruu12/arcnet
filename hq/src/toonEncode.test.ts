/**
 * Node assert tests for generic TOON encoder.
 * Run: node --experimental-strip-types --test src/toonEncode.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { encodeToon, envelopeToToon, modelIntelToToon } from "./toon.ts";
import type { AgentModelsResponse } from "./types.ts";

describe("encodeToon", () => {
  it("encodes uniform object arrays tabularly", () => {
    const out = encodeToon([
      { id: "a", n: 1 },
      { id: "b", n: 2 },
    ]);
    assert.match(out, /rows\[2\]\{id,n\}:/);
    assert.match(out, /a,1/);
  });

  it("encodes agent-view envelope shape", () => {
    const out = envelopeToToon({
      view: "fleet",
      id: "all",
      generated_at: "2026-07-25T00:00:00Z",
      data: { agents: [{ agent_id: "agent_j", model: "gpt-5.6-luna" }] },
      links: { self: "/api/agent-view/fleet/all" },
      hints: { note: "bounded" },
    });
    assert.match(out, /view: fleet/);
    assert.match(out, /data:/);
    assert.match(out, /agent_j/);
  });
});

describe("modelIntelToToon", () => {
  it("includes catalog_highlights table when present", () => {
    const intel = {
      agent_id: "agent_j",
      current_model: "gpt-5.6-luna",
      catalog_version: "2026-07e",
      price_label: "catalog list-price estimate as of 2026-07e",
      models: [],
      usage_evidence: {
        session_count: 1,
        sessions_with_token_usage: 1,
        input_tokens: 10,
        output_tokens: 5,
        total_tokens: 15,
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
      candidates: [],
      catalog_highlights: [
        {
          id: "kimi-k2.7-code",
          provider: "moonshot",
          capability_tier: "high",
          cost_class: "standard",
          tier: "high",
          status: "current",
          input_usd_per_mtok: 3,
          cached_input_usd_per_mtok: 0.3,
          output_usd_per_mtok: 15,
          context_window: 256000,
          reasoning: true,
          strengths: "coding",
          caveats: [],
          price_verified: "2026-07-25",
          projected_cost_usd: 0.02,
          projected_cost_delta: 0.01,
          price_label: "x",
          is_current: false,
          bucket: "peer",
        },
      ],
      reasoning_recommendation: null,
      honesty: "",
    } as AgentModelsResponse;
    const out = modelIntelToToon(intel);
    assert.match(out, /catalog_version: 2026-07e/);
    assert.match(out, /catalog_highlights\[1\]\{/);
    assert.match(out, /kimi-k2\.7-code/);
  });
});
