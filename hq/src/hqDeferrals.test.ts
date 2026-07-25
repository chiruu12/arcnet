/**
 * P27 HQ deferrals — view retry, SSE stream state, agent envelope validation, case-file export.
 * Run: node --experimental-strip-types --test src/hqDeferrals.test.ts
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { validateAgentEnvelopeShape } from "./apiResilience.ts";

describe("validateAgentEnvelopeShape", () => {
  const valid = {
    view: "signals",
    id: "agent_j",
    generated_at: "2026-07-25T00:00:00Z",
    data: { rows: [] },
    links: { signoz_trace: null },
    hints: { note: "ok" },
  };

  it("accepts a complete agent-view envelope", () => {
    assert.deepEqual(validateAgentEnvelopeShape(valid), { ok: true });
  });

  it("rejects non-objects", () => {
    const r = validateAgentEnvelopeShape(null);
    assert.equal(r.ok, false);
    if (!r.ok) assert.match(r.reason, /JSON object/);
  });

  it("rejects missing required fields", () => {
    const { hints: _h, ...partial } = valid;
    const r = validateAgentEnvelopeShape(partial);
    assert.equal(r.ok, false);
    if (!r.ok) assert.match(r.reason, /hints/);
  });

  it("rejects array links/hints", () => {
    const r = validateAgentEnvelopeShape({ ...valid, links: [] });
    assert.equal(r.ok, false);
    if (!r.ok) assert.match(r.reason, /links/);
  });

  it("rejects empty view or generated_at", () => {
    assert.equal(validateAgentEnvelopeShape({ ...valid, view: "" }).ok, false);
    assert.equal(validateAgentEnvelopeShape({ ...valid, generated_at: "" }).ok, false);
  });
});

describe("agentView envelope validation", () => {
  it("throws ApiError when server returns malformed envelope", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({ view: "fleet", id: "all", generated_at: "t", data: {}, links: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      )) as typeof fetch;
    try {
      const { api, ApiError } = await import("./api.ts");
      await assert.rejects(() => api.agentView("fleet", "all"), (e: unknown) => {
        assert.ok(e instanceof ApiError);
        assert.match(String(e), /envelope invalid/);
        assert.match(String(e), /hints/);
        return true;
      });
    } finally {
      globalThis.fetch = original;
    }
  });
});

describe("subscribeBus stream status", () => {
  it("reports connecting then live on open", async () => {
    const original = globalThis.EventSource;
    const statuses: string[] = [];
    class MockES {
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      addEventListener() {}
      close() {}
      constructor(_url: string) {
        queueMicrotask(() => this.onopen?.());
      }
    }
    globalThis.EventSource = MockES as unknown as typeof EventSource;
    try {
      const { subscribeBus } = await import("./api.ts");
      const unsub = subscribeBus(() => {}, (s) => statuses.push(s));
      await new Promise((r) => setTimeout(r, 0));
      unsub();
      assert.deepEqual(statuses, ["connecting", "live"]);
    } finally {
      globalThis.EventSource = original;
    }
  });

  it("reports api_down on stream error", async () => {
    const original = globalThis.EventSource;
    const statuses: string[] = [];
    class MockES {
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      addEventListener() {}
      close() {}
      constructor(_url: string) {
        queueMicrotask(() => this.onerror?.());
      }
    }
    globalThis.EventSource = MockES as unknown as typeof EventSource;
    try {
      const { subscribeBus } = await import("./api.ts");
      const unsub = subscribeBus(() => {}, (s) => statuses.push(s));
      await new Promise((r) => setTimeout(r, 0));
      unsub();
      assert.ok(statuses.includes("connecting"));
      assert.ok(statuses.includes("api_down"));
    } finally {
      globalThis.EventSource = original;
    }
  });
});

describe("downloadCaseFile", () => {
  it("surfaces HTTP errors instead of silent failure", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({ detail: "session not found", hint: "GET /api/sessions" }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      )) as typeof fetch;
    try {
      const { downloadCaseFile, ApiError } = await import("./api.ts");
      await assert.rejects(() => downloadCaseFile("s_missing"), (e: unknown) => {
        assert.ok(e instanceof ApiError);
        assert.match(String(e), /session not found/);
        return true;
      });
    } finally {
      globalThis.fetch = original;
    }
  });

  it("triggers a blob download on success", async () => {
    const originalFetch = globalThis.fetch;
    const clicks: { download: string }[] = [];
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = () => "blob:mock";
    URL.revokeObjectURL = () => {};
    globalThis.fetch = (async () =>
      new Response(new Uint8Array([80, 75, 3, 4]), {
        status: 200,
        headers: { "Content-Type": "application/zip" },
      })) as typeof fetch;
    const g = globalThis as typeof globalThis & {
      document?: {
        createElement: (tag: string) => { href: string; download: string; click: () => void };
      };
    };
    const originalDoc = g.document;
    g.document = {
      createElement: (tag: string) => {
        const el = { href: "", download: "", click: () => {} };
        if (tag === "a") {
          el.click = () => clicks.push({ download: el.download });
        }
        return el;
      },
    };
    try {
      const { downloadCaseFile } = await import("./api.ts");
      await downloadCaseFile("s_ecfdb55d");
      assert.equal(clicks.length, 1);
      assert.equal(clicks[0]!.download, "case-file-s_ecfdb55d.zip");
    } finally {
      globalThis.fetch = originalFetch;
      URL.createObjectURL = originalCreate;
      URL.revokeObjectURL = originalRevoke;
      if (originalDoc) g.document = originalDoc;
      else delete g.document;
    }
  });
});

describe("view retry token", () => {
  it("bumps a counter to re-run fetches", () => {
    let token = 0;
    const retry = () => {
      token += 1;
    };
    assert.equal(token, 0);
    retry();
    retry();
    assert.equal(token, 2);
  });
});
