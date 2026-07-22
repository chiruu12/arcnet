/**
 * Node assert tests for cascade reducer (no vitest in repo).
 * Run: node --experimental-strip-types --test src/cascade.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  cascadeReducer,
  emptyCascade,
  preferHeroSession,
  preferVersion,
} from "./cascade.ts";

describe("cascadeReducer", () => {
  it("set_agent clears version model session", () => {
    const prev = {
      agentId: "a",
      versionId: "v1",
      model: "gpt-4o",
      sessionId: "s1",
      lane: "versioned" as const,
    };
    const next = cascadeReducer(prev, { type: "set_agent", agentId: "b" });
    assert.deepEqual(next, {
      agentId: "b",
      versionId: "",
      model: "",
      sessionId: "",
      lane: "versioned",
    });
  });

  it("set_version clears session and may set model", () => {
    const prev = {
      ...emptyCascade(),
      agentId: "a",
      model: "old",
      sessionId: "s1",
    };
    const next = cascadeReducer(prev, {
      type: "set_version",
      versionId: "av_1",
      model: "gpt-4o-mini",
    });
    assert.equal(next.versionId, "av_1");
    assert.equal(next.model, "gpt-4o-mini");
    assert.equal(next.sessionId, "");
    assert.equal(next.lane, "versioned");
  });

  it("set_version with empty model clears stale model", () => {
    const prev = {
      ...emptyCascade(),
      agentId: "a",
      model: "old-model",
      sessionId: "s1",
    };
    const next = cascadeReducer(prev, {
      type: "set_version",
      versionId: "av_2",
      model: "",
    });
    assert.equal(next.model, "");
    assert.equal(next.sessionId, "");
  });

  it("set_unversioned without model preserves current model", () => {
    const prev = {
      ...emptyCascade(),
      agentId: "a",
      model: "gpt-4o",
      sessionId: "s1",
    };
    const next = cascadeReducer(prev, { type: "set_unversioned" });
    assert.equal(next.lane, "unversioned");
    assert.equal(next.versionId, "");
    assert.equal(next.model, "gpt-4o");
    assert.equal(next.sessionId, "");
  });

  it("set_unversioned labels honest fallback lane", () => {
    const next = cascadeReducer(emptyCascade(), {
      type: "set_unversioned",
      model: "gpt-4o",
    });
    assert.equal(next.lane, "unversioned");
    assert.equal(next.versionId, "");
    assert.equal(next.model, "gpt-4o");
  });

  it("set_model clears session only", () => {
    const prev = {
      agentId: "a",
      versionId: "v",
      model: "m1",
      sessionId: "s",
      lane: "versioned" as const,
    };
    const next = cascadeReducer(prev, { type: "set_model", model: "m2" });
    assert.equal(next.model, "m2");
    assert.equal(next.sessionId, "");
    assert.equal(next.versionId, "v");
  });
});

describe("prefer helpers", () => {
  it("preferHeroSession keeps prefer then heroes", () => {
    const ids = ["s_x", "s_ecfdb55d", "s_2af44726"];
    assert.equal(preferHeroSession(ids, ["s_ecfdb55d", "s_2af44726"], "s_x"), "s_x");
    assert.equal(preferHeroSession(ids, ["s_ecfdb55d", "s_2af44726"]), "s_ecfdb55d");
  });

  it("preferVersion picks deep-link or newest", () => {
    assert.equal(preferVersion(["av_new", "av_old"], "av_old"), "av_old");
    assert.equal(preferVersion(["av_new", "av_old"]), "av_new");
  });
});
