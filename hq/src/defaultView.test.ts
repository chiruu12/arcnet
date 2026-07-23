/**
 * Node assert tests for default view resolution.
 * Run: node --experimental-strip-types --test src/defaultView.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { resolveViewFromPath } from "./defaultView.ts";

describe("resolveViewFromPath", () => {
  it("defaults empty path to home", () => {
    assert.equal(resolveViewFromPath(""), "home");
    assert.equal(resolveViewFromPath("   "), "home");
  });

  it("keeps known deep-link views", () => {
    assert.equal(resolveViewFromPath("fleet_health"), "fleet_health");
    assert.equal(resolveViewFromPath("time_machine"), "time_machine");
    assert.equal(resolveViewFromPath("hq_agent"), "hq_agent");
  });

  it("falls back unknown paths to home", () => {
    assert.equal(resolveViewFromPath("not_a_view"), "home");
  });
});
