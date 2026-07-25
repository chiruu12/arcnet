/**
 * Node assert tests for Time Machine model vs prompt swap helpers.
 * Run: node --experimental-strip-types --test src/replaySwap.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  canRunReplaySwap,
  replayHistoryLabel,
  replaySwapAxis,
  replaySwapAxisTag,
  replaySwapChoice,
  replaySwapValidationMessage,
} from "./replaySwap.ts";
import type { ReplayRow } from "./apiResilience.ts";

describe("replaySwapAxis", () => {
  it("requires exactly one candidate field", () => {
    assert.equal(replaySwapAxis("gpt-4o", ""), "model");
    assert.equal(replaySwapAxis("", "hardened prompt"), "prompt");
    assert.equal(replaySwapAxis("", ""), "none");
    assert.equal(replaySwapAxis("gpt-4o", "also prompt"), "both");
  });
});

describe("replaySwapChoice", () => {
  it("builds API body for model or prompt only", () => {
    assert.deepEqual(replaySwapChoice("gpt-4o", ""), { candidate_model: "gpt-4o" });
    assert.deepEqual(replaySwapChoice("", "You are Agent J."), {
      candidate_prompt: "You are Agent J.",
    });
    assert.equal(replaySwapChoice("", ""), null);
    assert.equal(replaySwapChoice("m", "p"), null);
  });
});

describe("canRunReplaySwap", () => {
  it("blocks both-empty and both-filled", () => {
    assert.equal(canRunReplaySwap("gpt-4o", ""), true);
    assert.equal(canRunReplaySwap("", "prompt"), true);
    assert.equal(canRunReplaySwap("", ""), false);
    assert.equal(canRunReplaySwap("m", "p"), false);
  });
});

describe("replaySwapValidationMessage", () => {
  it("surfaces server-aligned validation text", () => {
    assert.match(
      replaySwapValidationMessage("m", "p")!,
      /exactly one of candidate_model or candidate_prompt/,
    );
    assert.match(replaySwapValidationMessage("", "")!, /pick candidate_model or candidate_prompt/);
  });
});

describe("replay history labels", () => {
  const base: ReplayRow = {
    replay_id: "r_1",
    session_id: "s_1",
    candidate_model: null,
    candidate_prompt_ref: null,
    verdict: {
      replay_id: "r_1",
      session_id: "s_1",
      baseline: {},
      candidate: {},
      divergences: [],
      verdict: "improved",
      confidence: "3/3",
      recommendation: "",
    },
    created_at: 1,
    duration_ms: 1,
  };

  it("tags model vs prompt axis in history rows", () => {
    assert.equal(
      replayHistoryLabel({ ...base, candidate_model: "gpt-4o-mini" }),
      "model=gpt-4o-mini",
    );
    assert.equal(
      replayHistoryLabel({ ...base, candidate_prompt_ref: "agents/prompts/j.md@abc" }),
      "prompt=agents/prompts/j.md@abc",
    );
    assert.equal(replaySwapAxisTag("model"), "[model-swap]");
    assert.equal(replaySwapAxisTag("prompt"), "[prompt-swap]");
  });
});

describe("runReplay request shape", () => {
  it("POSTs candidate_prompt to /api/replay", async () => {
    (import.meta as { env?: { VITE_ARCNET_API?: string } }).env = { VITE_ARCNET_API: "" };
    const calls: { url: string; body: string }[] = [];
    const original = globalThis.fetch;
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({
        url: String(input),
        body: String(init?.body ?? ""),
      });
      return new Response(
        JSON.stringify({
          replay_id: "r_1",
          session_id: "s_1",
          baseline: {},
          candidate: {},
          divergences: [],
          verdict: "improved",
          confidence: "3/3",
          recommendation: "ok",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }) as typeof fetch;
    try {
      const { api } = await import("./api.ts");
      const verdict = await api.runReplay("s_1", { candidate_prompt: "hardened" });
      assert.equal(calls.length, 1);
      assert.match(calls[0]!.url, /\/api\/replay$/);
      const body = JSON.parse(calls[0]!.body);
      assert.equal(body.session_id, "s_1");
      assert.equal(body.candidate_prompt, "hardened");
      assert.equal(body.candidate_model, undefined);
      assert.equal(verdict.verdict, "improved");
    } finally {
      globalThis.fetch = original;
    }
  });
});
