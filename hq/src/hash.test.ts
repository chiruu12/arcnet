/**
 * Node assert tests for hash parse/format (deep-link cascade state).
 * Run: node --experimental-strip-types --test src/hash.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatHash, parseHash, type HashState } from "./hash.ts";

describe("parseHash", () => {
  it("defaults to fleet_health", () => {
    assert.equal(parseHash("").view, "fleet_health");
    assert.equal(parseHash("#").view, "fleet_health");
  });

  it("parses cascade query keys", () => {
    const h = parseHash(
      "#case_files?agent=agent_j&version=av_1&model=gpt-4o&session=s_ecfdb55d",
    );
    assert.equal(h.view, "case_files");
    assert.equal(h.agent, "agent_j");
    assert.equal(h.version, "av_1");
    assert.equal(h.model, "gpt-4o");
    assert.equal(h.session, "s_ecfdb55d");
  });

  it("ignores unknown views", () => {
    assert.equal(parseHash("#not_a_view").view, "fleet_health");
  });

  it("omits empty query values", () => {
    const h = parseHash("#hq_agent?agent=agent_j&version=&session=");
    assert.equal(h.agent, "agent_j");
    assert.equal(h.version, undefined);
    assert.equal(h.session, undefined);
  });
});

describe("formatHash", () => {
  it("round-trips cascade fields", () => {
    const state: HashState = {
      view: "time_machine",
      agent: "agent_j",
      version: "av_x",
      model: "gpt-4o-mini",
      session: "s_2af44726",
    };
    const raw = formatHash(state);
    assert.equal(raw.startsWith("#time_machine?"), true);
    assert.deepEqual(parseHash(raw), state);
  });

  it("omits empty keys", () => {
    assert.equal(formatHash({ view: "signals" }), "#signals");
    assert.equal(
      formatHash({ view: "signals", agent: "agent_j" }),
      "#signals?agent=agent_j",
    );
  });
});
