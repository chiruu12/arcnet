/**
 * Node assert tests for model-intelligence parsing helpers.
 * Run: node --experimental-strip-types --test src/modelIntel.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatCostDelta, normalizeAgentModelsResponse } from "./modelIntel.ts";

describe("normalizeAgentModelsResponse", () => {
  it("accepts legacy bare array", () => {
    const out = normalizeAgentModelsResponse([
      { model: "gpt-4o-mini", session_count: 2, latest_started_at: 1 },
    ]);
    assert.equal(out.models.length, 1);
    assert.equal(out.models[0]?.model, "gpt-4o-mini");
    assert.equal(out.candidates.length, 0);
  });

  it("parses object payload with candidates and reasoning", () => {
    const out = normalizeAgentModelsResponse({
      agent_id: "agent_j",
      current_model: "gpt-4o-mini",
      catalog_version: "2026-07",
      price_label: "catalog list-price estimate as of 2026-07",
      models: [{ model: "gpt-4o-mini", session_count: 3, latest_started_at: null }],
      usage_evidence: {
        session_count: 3,
        sessions_with_token_usage: 2,
        input_tokens: 1000,
        output_tokens: 500,
        total_tokens: 1500,
      },
      workload_evidence: {
        session_count: 3,
        threat_count: 2,
        threat_rate: 0.6667,
        replay_count: 1,
        verdict_counts: { improved: 1 },
        adversarial_replay_count: 1,
      },
      baseline_projected_cost_usd: 0.00045,
      candidates: [
        {
          id: "gpt-4o-mini",
          provider: "openai",
          tier: "fast",
          input_usd_per_mtok: 0.15,
          output_usd_per_mtok: 0.6,
          context_window: 128000,
          reasoning: false,
          strengths: "cheap",
          projected_cost_usd: 0.00045,
          projected_cost_delta: 0,
          price_label: "catalog list-price estimate as of 2026-07",
          is_current: true,
        },
        {
          id: "o4-mini",
          provider: "openai",
          tier: "reasoning",
          input_usd_per_mtok: 1.1,
          output_usd_per_mtok: 4.4,
          context_window: 200000,
          reasoning: true,
          strengths: "tools",
          projected_cost_usd: 0.0033,
          projected_cost_delta: 0.00285,
          price_label: "catalog list-price estimate as of 2026-07",
          is_current: false,
        },
      ],
      reasoning_recommendation: {
        recommend: true,
        model_id: "o4-mini",
        tier: "reasoning",
        rationale: "recorded threat_rate=0.67",
        evidence: { threat_count: 2 },
        price_label: "catalog list-price estimate as of 2026-07",
      },
      honesty: "list-price only",
    });
    assert.equal(out.catalog_version, "2026-07");
    assert.equal(out.candidates.length, 2);
    assert.equal(out.candidates[1]?.tier, "reasoning");
    assert.equal(out.reasoning_recommendation?.model_id, "o4-mini");
    assert.equal(out.usage_evidence.input_tokens, 1000);
  });
});

describe("formatCostDelta", () => {
  it("formats savings and increases", () => {
    assert.equal(formatCostDelta(-0.0123), "−$0.0123");
    assert.equal(formatCostDelta(1.5), "+$1.50");
    assert.equal(formatCostDelta(0), "$0");
    assert.equal(formatCostDelta(null), "—");
  });
});
