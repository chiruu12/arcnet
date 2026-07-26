/**
 * Node assert tests for model-intelligence parsing helpers.
 * Run: node --experimental-strip-types --test src/modelIntel.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  bucketLabel,
  formatCostDelta,
  formatPricePerMtok,
  normalizeAgentModelsResponse,
} from "./modelIntel.ts";

describe("normalizeAgentModelsResponse", () => {
  it("accepts legacy bare array", () => {
    const out = normalizeAgentModelsResponse([
      { model: "legacy-baseline-v1", session_count: 2, latest_started_at: 1 },
    ]);
    assert.equal(out.models.length, 1);
    assert.equal(out.models[0]?.model, "legacy-baseline-v1");
    assert.equal(out.candidates.length, 0);
  });

  it("parses object payload with candidates and reasoning", () => {
    const out = normalizeAgentModelsResponse({
      agent_id: "agent_j",
      current_model: "legacy-baseline-v1",
      catalog_version: "2026-07e",
      price_label: "catalog list-price estimate as of 2026-07e",
      models: [{ model: "legacy-baseline-v1", session_count: 3, latest_started_at: null }],
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
      recommendation_buckets: {
        recommended_upgrade: [
          {
            id: "gpt-5.6-terra",
            provider: "openai",
            capability_tier: "high",
            cost_class: "standard",
            tier: "high",
            status: "current",
            input_usd_per_mtok: 2.5,
            cached_input_usd_per_mtok: 0.25,
            output_usd_per_mtok: 15,
            context_window: 1050000,
            max_output_tokens: 128000,
            reasoning: true,
            strengths: "balanced",
            caveats: [],
            price_verified: "2026-07-25",
            projected_cost_usd: 0.01,
            projected_cost_usd_cached: 0.001,
            projected_cost_delta: 0.009,
            price_label: "catalog list-price estimate as of 2026-07e",
            is_current: false,
            bucket: "recommended_upgrade",
          },
        ],
        cost_saver: [],
        peer: [],
        not_advised: [],
      },
      candidates: [
        {
          id: "legacy-baseline-v1",
          provider: "openai",
          capability_tier: "light",
          cost_class: "economy",
          tier: "light",
          status: "legacy",
          input_usd_per_mtok: 0.15,
          cached_input_usd_per_mtok: 0.015,
          output_usd_per_mtok: 0.6,
          context_window: 128000,
          max_output_tokens: 16384,
          reasoning: false,
          strengths: "cheap",
          caveats: [],
          price_verified: null,
          projected_cost_usd: 0.00045,
          projected_cost_usd_cached: 0.00004,
          projected_cost_delta: 0,
          price_label: "catalog list-price estimate as of 2026-07e",
          is_current: true,
        },
      ],
      reasoning_recommendation: {
        recommend: true,
        model_id: "gpt-5.6-terra",
        capability_tier: "high",
        tier: "high",
        summary: "recorded workload looks hard",
        evidence: [{ kind: "threat_density", threat_count: 2 }],
        price_label: "catalog list-price estimate as of 2026-07e",
      },
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
          max_output_tokens: 131072,
          reasoning: true,
          strengths: "coding",
          caveats: [],
          price_verified: "2026-07-25",
          projected_cost_usd: 0.02,
          projected_cost_usd_cached: 0.002,
          projected_cost_delta: 0.01,
          price_label: "catalog list-price estimate as of 2026-07e",
          is_current: false,
          bucket: "peer",
        },
      ],
      honesty: "list-price only",
    });
    assert.equal(out.catalog_version, "2026-07e");
    assert.equal(out.candidates.length, 1);
    assert.equal(out.candidates[0]?.status, "legacy");
    assert.equal(out.recommendation_buckets?.recommended_upgrade.length, 1);
    assert.equal(out.reasoning_recommendation?.model_id, "gpt-5.6-terra");
    assert.equal(out.usage_evidence.input_tokens, 1000);
    assert.equal(out.catalog_highlights?.length, 1);
    assert.equal(out.catalog_highlights?.[0]?.id, "kimi-k2.7-code");
  });

  it("defaults catalog_highlights to empty when absent", () => {
    const out = normalizeAgentModelsResponse({
      agent_id: "a",
      current_model: null,
      catalog_version: "2026-07e",
      price_label: "x",
      models: [],
      candidates: [],
      honesty: "",
    });
    assert.deepEqual(out.catalog_highlights, []);
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

describe("formatPricePerMtok", () => {
  it("formats catalog rates", () => {
    assert.equal(formatPricePerMtok(2.5), "$2.50");
    assert.equal(formatPricePerMtok(0.15), "$0.150");
    assert.equal(formatPricePerMtok(0), "—");
  });
});

describe("bucketLabel", () => {
  it("maps bucket keys", () => {
    assert.equal(bucketLabel("recommended_upgrade"), "recommended upgrade");
  });
});
