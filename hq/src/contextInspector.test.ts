/**
 * Context inspector — ingest order, provenance linking, twin builder.
 * Run: node --experimental-strip-types --test src/contextInspector.test.ts
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import {
  buildContextInspectorTwin,
  buildIngestTimeline,
  ingestSummary,
  sortSourcesIngestOrder,
  threatsLinkedToSource,
  unlinkedThreats,
} from "./contextInspector.ts";
import type { SourceRow } from "./types.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const heroes = JSON.parse(
  readFileSync(join(__dirname, "../../fixtures/heroes.json"), "utf8"),
) as {
  tables: { sources: SourceRow[]; threats: Array<Record<string, unknown>> };
};

function heroThreats() {
  return heroes.tables.threats
    .filter((t) => t.session_id === "s_ecfdb55d")
    .map((t) => ({
      threat_id: String(t.threat_id),
      session_id: String(t.session_id),
      checkpoint: String(t.checkpoint),
      action: String(t.action),
      category: String(t.category),
      subcategory: String(t.subcategory),
      risk_score: Number(t.risk_score),
      trust_level: String(t.trust_level),
      evidence_excerpt: String(t.evidence),
      created_at: Number(t.created_at),
    }));
}

function heroSources() {
  return heroes.tables.sources.filter((s) => s.session_id === "s_ecfdb55d");
}

describe("sortSourcesIngestOrder", () => {
  it("orders oldest created_at first", () => {
    const rows = heroSources();
    const ordered = sortSourcesIngestOrder(rows);
    assert.equal(ordered[0]?.source_id, "src_2eb911a6");
    assert.equal(ordered.at(-1)?.source_id, "src_981d9937");
  });
});

describe("threatsLinkedToSource", () => {
  it("links taint block to fetch_url retrieved source on hero session", () => {
    const sources = sortSourcesIngestOrder(heroSources());
    const threats = heroThreats();
    const fetch = sources.find((s) => s.origin === "fetch_url");
    assert.ok(fetch);
    const linked = threatsLinkedToSource(fetch, threats);
    assert.equal(linked.length, 1);
    assert.equal(linked[0]?.subcategory, "retrieved_source_in_side_effect");
    assert.equal(linked[0]?.risk_score, 0.85);
  });

  it("does not link user-trust sources to taint threats", () => {
    const sources = sortSourcesIngestOrder(heroSources());
    const threats = heroThreats();
    const user = sources.find((s) => s.trust_level === "user");
    assert.ok(user);
    assert.equal(threatsLinkedToSource(user, threats).length, 0);
  });
});

describe("ingestSummary", () => {
  it("narrates clean ingest with downstream block for hero session", () => {
    const summary = ingestSummary(heroSources(), heroThreats());
    assert.equal(summary.ingestClean, true);
    assert.match(summary.narrative, /clean at ingest/);
    assert.match(summary.narrative, /blocked at tool_call/);
    assert.equal(summary.downstreamBlock?.subcategory, "retrieved_source_in_side_effect");
  });
});

describe("buildIngestTimeline", () => {
  it("places provenance under the retrieved fetch_url step", () => {
    const timeline = buildIngestTimeline(heroSources(), heroThreats());
    const withLink = timeline.filter((s) => s.linkedThreats.length > 0);
    assert.equal(withLink.length, 2);
    assert.ok(withLink.every((s) => s.source.origin === "fetch_url"));
  });
});

describe("unlinkedThreats", () => {
  it("keeps trajectory threats separate from source provenance", () => {
    const orphans = unlinkedThreats(heroSources(), heroThreats());
    assert.equal(orphans.length, 2);
    assert.ok(orphans.every((t) => t.category === "trajectory"));
  });
});

describe("buildContextInspectorTwin", () => {
  it("emits machine-readable context_inspector envelope", () => {
    const twin = buildContextInspectorTwin("s_ecfdb55d", heroSources(), heroThreats());
    assert.equal(twin.view, "context_inspector");
    assert.equal(twin.id, "s_ecfdb55d");
    assert.equal(twin.data.summary.ingestClean, true);
    assert.equal(twin.links.threats, "/api/agent-view/threats/s_ecfdb55d");
    assert.ok(Array.isArray(twin.data.ingest_timeline));
  });
});

describe("resolveViewFromPath", () => {
  it("registers context_inspector hash route", async () => {
    const { resolveViewFromPath } = await import("./defaultView.ts");
    assert.equal(resolveViewFromPath("context_inspector"), "context_inspector");
  });
});
