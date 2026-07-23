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
  "HITL decide updates SQLite only; does not pause a live AgentOS run (relay = future work).";
