/**
 * Node assert tests for SigNoz dashboard deep-link helpers.
 * Run: node --experimental-strip-types --test src/dashboardLinks.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  dashboardLinkPath,
  dashboardUuid,
  resolveDashboardLinks,
  signozBaseUrl,
  type DashboardLinkDef,
} from "./dashboardLinks.ts";

const DASH_LINK: DashboardLinkDef = {
  name: "fleet_overview",
  key: "fleet_ops",
  path: "/dashboard",
  desc: "fleet",
};

describe("dashboardUuid", () => {
  it("prefers status dashboards over env", () => {
    const id = dashboardUuid(
      { dashboards: { fleet_ops: "uuid-from-status" } },
      "fleet_ops",
      { fleet_ops: "uuid-from-env" },
    );
    assert.equal(id, "uuid-from-status");
  });

  it("falls back to env when status missing", () => {
    assert.equal(
      dashboardUuid(null, "fleet_ops", { fleet_ops: "uuid-from-env" }),
      "uuid-from-env",
    );
  });
});

describe("dashboardLinkPath", () => {
  it("deep-links when uuid resolves", () => {
    assert.equal(
      dashboardLinkPath({ dashboards: { fleet_ops: "abc-123" } }, DASH_LINK),
      "/dashboard/abc-123",
    );
  });

  it("falls back to generic path when uuid missing", () => {
    assert.equal(dashboardLinkPath(null, DASH_LINK), "/dashboard");
  });
});

describe("resolveDashboardLinks", () => {
  it("marks named boards unresolved without uuid", () => {
    const links = resolveDashboardLinks(null, "http://localhost:8080", [DASH_LINK]);
    assert.equal(links.length, 1);
    assert.equal(links[0]!.resolved, false);
    assert.equal(links[0]!.href, "");
  });

  it("builds per-board href when uuid resolves", () => {
    const links = resolveDashboardLinks(
      { signoz_url: "http://signoz:8080/", dashboards: { fleet_ops: "fleet-uuid" } },
      "http://localhost:8080",
      [DASH_LINK],
    );
    assert.equal(links[0]!.resolved, true);
    assert.equal(links[0]!.href, "http://signoz:8080/dashboard/fleet-uuid");
    assert.equal(links[0]!.uuid, "fleet-uuid");
  });

  it("keeps non-dashboard links always resolved", () => {
    const links = resolveDashboardLinks(null, "http://localhost:8080", [
      { name: "traces", path: "/traces-explorer", desc: "traces" },
    ]);
    assert.equal(links[0]!.resolved, true);
    assert.equal(links[0]!.href, "http://localhost:8080/traces-explorer");
  });
});

describe("signozBaseUrl", () => {
  it("strips trailing slash", () => {
    assert.equal(signozBaseUrl({ signoz_url: "http://signoz:8080/" }, "http://x"), "http://signoz:8080");
  });
});
