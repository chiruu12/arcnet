/**
 * Node assert tests for shell API recover helpers.
 * Run: node --experimental-strip-types --test src/apiRecover.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  API_RECOVER_INTERVAL_MS,
  apiBreadcrumbStatus,
  shouldRecoverProbe,
} from "./apiRecover.ts";

describe("shouldRecoverProbe", () => {
  it("probes again only when api_down", () => {
    assert.equal(shouldRecoverProbe(false), true);
    assert.equal(shouldRecoverProbe(true), false);
    assert.equal(shouldRecoverProbe(null), false);
  });
});

describe("apiBreadcrumbStatus", () => {
  it("maps probe state to breadcrumb suffix", () => {
    assert.equal(apiBreadcrumbStatus(null), "connecting");
    assert.equal(apiBreadcrumbStatus(true), "live");
    assert.equal(apiBreadcrumbStatus(false), "api_down");
  });
});

describe("API_RECOVER_INTERVAL_MS", () => {
  it("stays within the 15–30s recovery window", () => {
    assert.ok(API_RECOVER_INTERVAL_MS >= 15_000);
    assert.ok(API_RECOVER_INTERVAL_MS <= 30_000);
  });
});
