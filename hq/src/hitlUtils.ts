import type { HitlRelayStatus } from "./types";

/** One-line operator summary of a HITL payload object. */
export function hitlPayloadSummary(payload: unknown): string {
  if (payload == null) return "—";
  let obj: unknown = payload;
  if (typeof obj === "string") {
    const raw = obj;
    try {
      obj = JSON.parse(raw) as unknown;
    } catch {
      return raw.slice(0, 160);
    }
  }
  if (typeof obj === "object" && obj !== null) {
    const p = obj as Record<string, unknown>;
    const headline = p.reason ?? p.tool ?? p.action ?? p.name;
    if (headline != null && String(headline).trim()) {
      return String(headline).slice(0, 160);
    }
    return JSON.stringify(obj).slice(0, 160);
  }
  return String(obj).slice(0, 160);
}

export const HITL_RELAY_HONESTY =
  "Reject relays a kill on the signal bus and to AgentOS when ARCNET_AGENTOS_URL is set; approve records an acknowledgement only — live Agno pause/resume is not wired.";

/** One-line relay status for a decided HITL row. */
export function hitlRelaySummary(relay: HitlRelayStatus | null | undefined): string {
  if (!relay) return "—";
  if (!relay.attempted) return `not attempted · ${relay.detail || "relay disabled"}`;
  if (relay.delivered) return `delivered · ${relay.detail}`;
  return `not delivered · ${relay.detail}`;
}
