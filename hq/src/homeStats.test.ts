/**
 * Node assert tests for home landing stat helpers.
 * Run: node --experimental-strip-types --test src/homeStats.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  buildHomeStats,
  countAgents,
  countThreatsBlocked,
  formatStatValue,
} from "./homeStats.ts";
import type { FleetRow, ThreatRow } from "./types.ts";

const fleetRow = (id: string): FleetRow => ({
  agent_id: id,
  name: id,
  role: null,
  exposure: null,
  model: null,
  last_seen: null,
  health: {
    sessions_24h: 0,
    threats_24h: 0,
    blocked_24h: 0,
    cost_24h_usd: 0,
    anomalies_24h: 0,
    active_signals: 0,
  },
});

const threat = (action: string): ThreatRow => ({
  threat_id: `t_${action}`,
  session_id: null,
  agent_id: null,
  checkpoint: null,
  action,
  category: null,
  subcategory: null,
  risk_score: null,
  trust_level: null,
  created_at: null,
});

describe("countAgents", () => {
  it("returns null while loading", () => {
    assert.equal(countAgents(null), null);
  });

  it("counts fleet rows", () => {
    assert.equal(countAgents([fleetRow("a"), fleetRow("b")]), 2);
  });
});

describe("countThreatsBlocked", () => {
  it("counts block actions only", () => {
    const rows = [threat("block"), threat("allow"), threat("block")];
    assert.deepEqual(countThreatsBlocked(rows, 3), { count: 2, partial: false });
  });

  it("marks partial when page is truncated", () => {
    const rows = [threat("block")];
    assert.deepEqual(countThreatsBlocked(rows, 10), { count: 1, partial: true });
  });
});

describe("formatStatValue", () => {
  it("renders loading dash", () => {
    assert.equal(formatStatValue(null), "—");
  });

  it("renders partial blocked counts", () => {
    assert.equal(formatStatValue(3, true), "3+");
  });

  it("renders exact counts", () => {
    assert.equal(formatStatValue(12), "12");
  });
});

describe("buildHomeStats", () => {
  it("merges live API shapes", () => {
    const snap = buildHomeStats({
      fleet: [fleetRow("agent_j")],
      sessionsTotal: 42,
      threats: [threat("block"), threat("redact")],
      threatsTotal: 2,
      signalsTotal: 7,
      replays: [{}, {}],
    });
    assert.deepEqual(snap, {
      agents: 1,
      sessions: 42,
      threats_blocked: 1,
      threats_blocked_partial: false,
      signals: 7,
      replays: 2,
    });
  });
});
