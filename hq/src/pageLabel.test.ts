/**
 * Node assert tests for pagination label helper.
 * Run: node --experimental-strip-types --test src/pageLabel.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { showingOfTotal } from "./pageLabel.ts";

describe("showingOfTotal", () => {
  it("formats page under total", () => {
    assert.equal(showingOfTotal(40, 120), "showing 40 of 120");
  });

  it("formats when page equals total", () => {
    assert.equal(showingOfTotal(5, 5), "showing 5 of 5");
  });

  it("handles empty", () => {
    assert.equal(showingOfTotal(0, 0), "showing 0 of 0");
  });

  it("floors non-integers and clamps negatives", () => {
    assert.equal(showingOfTotal(-1, 3.9), "showing 0 of 3");
  });
});
