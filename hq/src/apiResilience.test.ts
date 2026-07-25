/**
 * Node assert tests for HQ API resilience helpers.
 * Run: node --experimental-strip-types --test src/apiResilience.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ApiError,
  asArray,
  formatApiErrorMessage,
  isOfflineError,
  normalizeFleetRow,
  normalizeFleetRows,
  normalizeCorpusScorecard,
  normalizeHitlRows,
  normalizeReplayRows,
  normalizeSessionRows,
  normalizeSignalRow,
  normalizeSignalRows,
  normalizeVerdict,
  parseErrorEnvelope,
  parseSsePayload,
  toUserError,
} from "./apiResilience.ts";

describe("parseErrorEnvelope", () => {
  it("parses detail and hint from JSON error body", () => {
    assert.deepEqual(
      parseErrorEnvelope('{"detail":"session missing","hint":"GET /api/sessions"}'),
      { detail: "session missing", hint: "GET /api/sessions" },
    );
  });

  it("returns null for non-JSON or missing detail", () => {
    assert.equal(parseErrorEnvelope("<html>502</html>"), null);
    assert.equal(parseErrorEnvelope('{"hint":"only"}'), null);
  });
});

describe("formatApiErrorMessage", () => {
  it("renders detail and hint inline", () => {
    const msg = formatApiErrorMessage(
      404,
      "/api/sessions/s_x",
      '{"detail":"not found","hint":"list ids via GET /api/sessions"}',
    );
    assert.equal(msg, "not found — list ids via GET /api/sessions");
  });

  it("falls back to status and body snippet", () => {
    const msg = formatApiErrorMessage(502, "/api/fleet", "Bad Gateway", "Bad Gateway");
    assert.match(msg, /502/);
    assert.match(msg, /Bad Gateway/);
  });
});

describe("asArray", () => {
  it("coerces null and objects to empty arrays", () => {
    assert.deepEqual(asArray(null), []);
    assert.deepEqual(asArray({}), []);
    assert.deepEqual(asArray("x"), []);
  });
});

describe("normalizeFleetRows", () => {
  it("drops rows missing agent_id and guards null health", () => {
    const rows = normalizeFleetRows([
      null,
      { agent_id: "a1", health: null },
      { agent_id: "a2", health: { threats_24h: "3" } },
    ]);
    assert.equal(rows.length, 2);
    assert.equal(rows[0]!.health.threats_24h, 0);
    assert.equal(rows[1]!.health.threats_24h, 3);
  });

  it("returns empty array when payload is not a list", () => {
    assert.deepEqual(normalizeFleetRows(null), []);
    assert.deepEqual(normalizeFleetRows({ agent_id: "solo" }), []);
  });

  it("normalizes latency fields on health", () => {
    const row = normalizeFleetRow({
      agent_id: "a1",
      health: {
        p50_wall_clock_ms_24h: "1200",
        p95_wall_clock_ms_24h: 3400,
        latency_sample_count_24h: "3",
        latency_source_24h: "ended_at-started_at",
      },
    });
    assert.equal(row!.health.p50_wall_clock_ms_24h, 1200);
    assert.equal(row!.health.p95_wall_clock_ms_24h, 3400);
    assert.equal(row!.health.latency_sample_count_24h, 3);
  });
});

describe("normalizeCorpusScorecard", () => {
  it("parses stored scorecard payload", () => {
    const card = normalizeCorpusScorecard({
      mode: "stored",
      session_count: 2,
      verdict_counts: { improved: "1", regressed: 1 },
      goals_reached: { baseline: 0, candidate: 2, of: 2 },
      cost_delta_usd_total: -0.01,
      cost_delta_pct_median: -25,
      steps_delta_median: -1,
      threat_resistance: { threat_sessions: 1, candidate_resisted: 1, rate: 1 },
      honesty: "offline",
    });
    assert.equal(card!.mode, "stored");
    assert.equal(card!.verdict_counts.improved, 1);
    assert.equal(card!.threat_resistance.rate, 1);
  });
});

describe("normalizeSignalRows", () => {
  it("filters malformed signal rows", () => {
    const rows = normalizeSignalRows([
      { signal_id: "sig_1", agent_id: "a1", kind: "kill" },
      { signal_id: "sig_2" },
      "bad",
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0]!.kind, "kill");
  });
});

describe("normalizeSessionRows", () => {
  it("accepts numeric strings for timestamps", () => {
    const rows = normalizeSessionRows([
      {
        session_id: "s_1",
        agent_id: "a1",
        status: "done",
        started_at: "1700000000000",
        has_transcript: "1",
      },
    ]);
    assert.equal(rows[0]!.started_at, 1700000000000);
    assert.equal(rows[0]!.has_transcript, 1);
  });
});

describe("normalizeVerdict", () => {
  it("coerces non-list divergences and missing verdict fields", () => {
    const v = normalizeVerdict({
      replay_id: "r1",
      session_id: "s1",
      divergences: "nope",
      verdict: null,
    });
    assert.ok(v);
    assert.deepEqual(v!.divergences, []);
    assert.equal(v!.verdict, "unknown");
  });
});

describe("normalizeReplayRows", () => {
  it("skips rows with malformed nested verdict", () => {
    const rows = normalizeReplayRows([
      {
        replay_id: "r1",
        session_id: "s1",
        verdict: { replay_id: "r1", session_id: "s1", verdict: "improved" },
      },
      { replay_id: "r2", session_id: "s2", verdict: null },
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0]!.verdict.verdict, "improved");
  });
});

describe("normalizeHitlRows", () => {
  it("keeps string payloads and defaults status", () => {
    const rows = normalizeHitlRows([
      {
        hitl_id: "h1",
        run_id: "run1",
        payload: '{"reason":"pause"}',
      },
    ]);
    assert.equal(rows[0]!.payload, '{"reason":"pause"}');
    assert.equal(rows[0]!.status, "unknown");
  });
});

describe("parseSsePayload", () => {
  it("returns null for invalid JSON or non-objects", () => {
    assert.equal(parseSsePayload("not-json"), null);
    assert.equal(parseSsePayload("[]"), null);
  });

  it("parses object frames", () => {
    assert.deepEqual(parseSsePayload('{"signal_id":"s1"}'), { signal_id: "s1" });
  });
});

describe("normalizeSignalRow (sse)", () => {
  it("guards partial live frames", () => {
    assert.equal(normalizeSignalRow({ signal_id: "s1" }), null);
    const row = normalizeSignalRow({
      signal_id: "s1",
      agent_id: "a1",
      kind: null,
    });
    assert.equal(row!.kind, "unknown");
  });
});

describe("offline errors", () => {
  it("detects fetch failures", () => {
    assert.equal(isOfflineError(new ApiError({ message: "x", offline: true })), true);
    assert.equal(isOfflineError(new TypeError("Failed to fetch")), true);
    assert.equal(isOfflineError(new Error("404")), false);
  });

  it("formats user-facing offline message", () => {
    const msg = toUserError(new ApiError({ message: "x", offline: true }));
    assert.match(msg, /unreachable/);
  });
});

describe("api request integration", () => {
  it("surfaces structured 401 envelope from fetch", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          detail: "write auth required",
          hint: "set X-Arcnet-Write-Secret",
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      )) as typeof fetch;
    try {
      const { api } = await import("./api.ts");
      await assert.rejects(() => api.fleet(), (e: unknown) => {
        assert.ok(e instanceof ApiError);
        assert.match(String(e), /write auth required/);
        assert.match(String(e), /X-Arcnet-Write-Secret/);
        return true;
      });
    } finally {
      globalThis.fetch = original;
    }
  });

  it("treats non-JSON 502 body as readable error", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response("<html>502 Bad Gateway</html>", {
        status: 502,
        headers: { "Content-Type": "text/html" },
      })) as typeof fetch;
    try {
      const { api } = await import("./api.ts");
      await assert.rejects(() => api.fleet(), (e: unknown) => {
        assert.ok(e instanceof ApiError);
        assert.match(String(e), /non-JSON|502|html/i);
        return true;
      });
    } finally {
      globalThis.fetch = original;
    }
  });

  it("normalizes null list payloads to empty arrays", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response("null", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    try {
      const { api } = await import("./api.ts");
      const fleet = await api.fleet();
      assert.deepEqual(fleet, []);
    } finally {
      globalThis.fetch = original;
    }
  });
});
