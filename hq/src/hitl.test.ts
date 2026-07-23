/**
 * Node assert tests for HITL helpers and decide API shape.
 * Run: node --experimental-strip-types --test src/hitl.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { HITL_RELAY_HONESTY, hitlPayloadSummary } from "./hitlUtils.ts";

describe("hitlPayloadSummary", () => {
  it("prefers reason from object payload", () => {
    assert.equal(
      hitlPayloadSummary({ reason: "pause before send_email", tool: "send_email" }),
      "pause before send_email",
    );
  });

  it("parses JSON string payloads", () => {
    assert.equal(
      hitlPayloadSummary('{"tool":"fetch_url","reason":"review retrieved content"}'),
      "review retrieved content",
    );
  });

  it("handles null", () => {
    assert.equal(hitlPayloadSummary(null), "—");
  });
});

describe("HITL relay honesty", () => {
  it("states SQLite-only relay", () => {
    assert.match(HITL_RELAY_HONESTY, /SQLite/);
    assert.match(HITL_RELAY_HONESTY, /does not pause a live AgentOS run/);
  });
});

describe("decideHitl request shape", () => {
  it("POSTs approved decision to /api/hitl/{id}", async () => {
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
          hitl_id: "hitl_abc12345",
          run_id: "run_1",
          session_id: "s_1",
          payload: { reason: "x" },
          status: "approved",
          created_at: 1,
          decided_at: 2,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }) as typeof fetch;
    try {
      const { api } = await import("./api.ts");
      const row = await api.decideHitl("hitl_abc12345", "approved");
      assert.equal(calls.length, 1);
      assert.match(calls[0]!.url, /\/api\/hitl\/hitl_abc12345$/);
      assert.equal(JSON.parse(calls[0]!.body).decision, "approved");
      assert.equal(row.status, "approved");
    } finally {
      globalThis.fetch = original;
    }
  });
});
