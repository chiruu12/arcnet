/**
 * HQ fetch resilience — error envelopes, payload guards, offline detection.
 * Pure helpers; tested offline without a live server.
 */

import type {
  AgentEnvelope,
  AgentModelRow,
  FleetRow,
  HitlRelayStatus,
  HitlRow,
  SessionRow,
  SignalRow,
  SourceRow,
  ThreatRow,
  Verdict,
} from "./types";

export type AgentVersionRow = {
  version_id: string;
  agent_id: string;
  version: string;
  model: string | null;
  model_version: string | null;
  source_ref: string | null;
  notes: string | null;
  created_at: number | null;
};

export type ReplayRow = {
  replay_id: string;
  session_id: string;
  candidate_model: string | null;
  candidate_prompt_ref: string | null;
  verdict: Verdict;
  created_at: number | null;
  duration_ms: number | null;
};

export type ApiErrorEnvelope = { detail: string; hint?: string };

/** Thrown by api.ts on HTTP / network / parse failures. */
export class ApiError extends Error {
  readonly status: number | null;
  readonly detail: string;
  readonly hint: string | null;
  readonly offline: boolean;
  readonly path: string;

  constructor(opts: {
    message: string;
    status?: number | null;
    detail?: string;
    hint?: string | null;
    offline?: boolean;
    path?: string;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status ?? null;
    this.detail = opts.detail ?? opts.message;
    this.hint = opts.hint ?? null;
    this.offline = Boolean(opts.offline);
    this.path = opts.path ?? "";
  }
}

export function asNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) {
    return Number(v);
  }
  return null;
}

export function asString(v: unknown): string | null {
  if (typeof v === "string") return v;
  if (v == null) return null;
  return String(v);
}

export function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {};
}

/** Coerce list endpoints that may return null / object / scalar. */
export function asArray(raw: unknown): unknown[] {
  if (Array.isArray(raw)) return raw;
  if (raw == null) return [];
  return [];
}

export function parseErrorEnvelope(text: string): ApiErrorEnvelope | null {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{")) return null;
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (!parsed || typeof parsed !== "object") return null;
    const o = parsed as Record<string, unknown>;
    const detail = asString(o.detail);
    if (!detail) return null;
    const hint = asString(o.hint) ?? undefined;
    return hint ? { detail, hint } : { detail };
  } catch {
    return null;
  }
}

export function formatApiErrorMessage(
  status: number,
  path: string,
  bodyText: string,
  statusText = "",
): string {
  const env = parseErrorEnvelope(bodyText);
  if (env) {
    return env.hint ? `${env.detail} — ${env.hint}` : env.detail;
  }
  const snippet = bodyText.trim().slice(0, 200);
  const base = `${status}${statusText ? ` ${statusText}` : ""} — ${path}`;
  return snippet ? `${base}: ${snippet}` : base;
}

export function isOfflineError(e: unknown): boolean {
  if (e instanceof ApiError) return e.offline;
  const msg = String(e);
  return (
    msg.includes("Failed to fetch") ||
    msg.includes("NetworkError") ||
    msg.includes("Load failed") ||
    msg.includes("Network request failed")
  );
}

export function toUserError(e: unknown, fallback = "request failed"): string {
  if (e instanceof ApiError) {
    if (e.offline) {
      return "arcnet-server unreachable — start uvicorn on :8000 and reload";
    }
    return e.message;
  }
  if (isOfflineError(e)) {
    return "arcnet-server unreachable — start uvicorn on :8000 and reload";
  }
  const msg = String(e);
  return msg || fallback;
}

export async function readJsonBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new ApiError({
      message: `non-JSON response from ${res.url || "server"}`,
      status: res.status,
      detail: text.trim().slice(0, 200) || "non-JSON body",
      path: "",
    });
  }
}

export function normalizeHealth(raw: unknown): FleetRow["health"] {
  const h = asRecord(raw);
  return {
    sessions_24h: asNum(h.sessions_24h) ?? 0,
    threats_24h: asNum(h.threats_24h) ?? 0,
    blocked_24h: asNum(h.blocked_24h) ?? 0,
    cost_24h_usd: asNum(h.cost_24h_usd) ?? 0,
    anomalies_24h: asNum(h.anomalies_24h) ?? 0,
    active_signals: asNum(h.active_signals) ?? 0,
  };
}

export function normalizeFleetRow(raw: unknown): FleetRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const agentId = asString(o.agent_id);
  if (!agentId) return null;
  return {
    agent_id: agentId,
    name: asString(o.name),
    role: asString(o.role),
    exposure: asString(o.exposure),
    model: asString(o.model),
    last_seen: asNum(o.last_seen),
    health: normalizeHealth(o.health),
  };
}

export function normalizeFleetRows(raw: unknown): FleetRow[] {
  return asArray(raw)
    .map(normalizeFleetRow)
    .filter((r): r is FleetRow => r != null);
}

export function normalizeSessionRow(raw: unknown): SessionRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const sessionId = asString(o.session_id);
  const agentId = asString(o.agent_id);
  if (!sessionId || !agentId) return null;
  const outcome = o.outcome;
  const usage = o.usage;
  return {
    session_id: sessionId,
    agent_id: agentId,
    scenario: asString(o.scenario),
    goal: asString(o.goal),
    model: asString(o.model),
    status: asString(o.status) ?? "unknown",
    outcome:
      outcome && typeof outcome === "object" && !Array.isArray(outcome)
        ? (outcome as Record<string, unknown>)
        : null,
    usage:
      usage && typeof usage === "object" && !Array.isArray(usage)
        ? (usage as Record<string, unknown>)
        : null,
    trace_id: asString(o.trace_id),
    agent_version: asString(o.agent_version),
    started_at: asNum(o.started_at),
    ended_at: asNum(o.ended_at),
    has_transcript: asNum(o.has_transcript) ?? 0,
  };
}

export function normalizeSessionRows(raw: unknown): SessionRow[] {
  return asArray(raw)
    .map(normalizeSessionRow)
    .filter((r): r is SessionRow => r != null);
}

export function normalizeSignalRow(raw: unknown): SignalRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const signalId = asString(o.signal_id);
  const agentId = asString(o.agent_id);
  if (!signalId || !agentId) return null;
  return {
    signal_id: signalId,
    session_id: asString(o.session_id),
    agent_id: agentId,
    kind: asString(o.kind) ?? "unknown",
    severity: asString(o.severity) ?? "—",
    reason: asString(o.reason) ?? "",
    guidance: asString(o.guidance),
    source: asString(o.source) ?? "",
    status: asString(o.status) ?? "unknown",
    created_at: asNum(o.created_at),
  };
}

export function normalizeSignalRows(raw: unknown): SignalRow[] {
  return asArray(raw)
    .map(normalizeSignalRow)
    .filter((r): r is SignalRow => r != null);
}

export function normalizeHitlRelay(raw: unknown): HitlRelayStatus | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.attempted !== "boolean" || typeof o.delivered !== "boolean") return null;
  return {
    attempted: o.attempted,
    delivered: o.delivered,
    detail: asString(o.detail) ?? "",
  };
}

export function normalizeHitlRow(raw: unknown): HitlRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const hitlId = asString(o.hitl_id);
  const runId = asString(o.run_id);
  if (!hitlId || !runId) return null;
  const payload = o.payload;
  return {
    hitl_id: hitlId,
    run_id: runId,
    session_id: asString(o.session_id),
    payload:
      payload == null || typeof payload === "string" || typeof payload === "object"
        ? (payload as HitlRow["payload"])
        : null,
    status: asString(o.status) ?? "unknown",
    created_at: asNum(o.created_at),
    decided_at: asNum(o.decided_at),
    relay: normalizeHitlRelay(o.relay),
  };
}

export function normalizeHitlRows(raw: unknown): HitlRow[] {
  return asArray(raw)
    .map(normalizeHitlRow)
    .filter((r): r is HitlRow => r != null);
}

export function normalizeSourceRow(raw: unknown): SourceRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const sourceId = asString(o.source_id);
  if (!sourceId) return null;
  return {
    source_id: sourceId,
    session_id: asString(o.session_id),
    agent_id: asString(o.agent_id),
    origin: asString(o.origin),
    trust_level: asString(o.trust_level),
    scan_action: asString(o.scan_action),
    findings: asNum(o.findings) ?? 0,
    created_at: asNum(o.created_at),
  };
}

export function normalizeSourceRows(raw: unknown): SourceRow[] {
  return asArray(raw)
    .map(normalizeSourceRow)
    .filter((r): r is SourceRow => r != null);
}

export function normalizeThreatRow(raw: unknown): ThreatRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const threatId = asString(o.threat_id);
  if (!threatId) return null;
  return {
    threat_id: threatId,
    session_id: asString(o.session_id),
    agent_id: asString(o.agent_id),
    checkpoint: asString(o.checkpoint),
    action: asString(o.action),
    category: asString(o.category),
    subcategory: asString(o.subcategory),
    risk_score: asNum(o.risk_score),
    trust_level: asString(o.trust_level),
    created_at: asNum(o.created_at),
  };
}

export function normalizeThreatRows(raw: unknown): ThreatRow[] {
  return asArray(raw)
    .map(normalizeThreatRow)
    .filter((r): r is ThreatRow => r != null);
}

export function normalizeAgentVersionRow(raw: unknown): AgentVersionRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const versionId = asString(o.version_id);
  const agentId = asString(o.agent_id);
  if (!versionId || !agentId) return null;
  return {
    version_id: versionId,
    agent_id: agentId,
    version: asString(o.version) ?? versionId,
    model: asString(o.model),
    model_version: asString(o.model_version),
    source_ref: asString(o.source_ref),
    notes: asString(o.notes),
    created_at: asNum(o.created_at),
  };
}

export function normalizeAgentVersionRows(raw: unknown): AgentVersionRow[] {
  return asArray(raw)
    .map(normalizeAgentVersionRow)
    .filter((r): r is AgentVersionRow => r != null);
}

export function normalizeDivergence(raw: unknown): { step: number; note: string } | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  return {
    step: asNum(o.step) ?? 0,
    note: asString(o.note) ?? "",
  };
}

export function normalizeVerdict(raw: unknown): Verdict | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const replayId = asString(o.replay_id);
  const sessionId = asString(o.session_id);
  if (!replayId || !sessionId) return null;
  const divergences = asArray(o.divergences)
    .map(normalizeDivergence)
    .filter((d): d is { step: number; note: string } => d != null);
  return {
    replay_id: replayId,
    session_id: sessionId,
    scenario: asString(o.scenario),
    baseline: asRecord(o.baseline),
    candidate: asRecord(o.candidate),
    divergences,
    verdict: asString(o.verdict) ?? "unknown",
    confidence: asString(o.confidence) ?? "—",
    recommendation: asString(o.recommendation) ?? "",
  };
}

export function normalizeReplayRow(raw: unknown): ReplayRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const replayId = asString(o.replay_id);
  const sessionId = asString(o.session_id);
  if (!replayId || !sessionId) return null;
  const verdict = normalizeVerdict(o.verdict);
  if (!verdict) return null;
  return {
    replay_id: replayId,
    session_id: sessionId,
    candidate_model: asString(o.candidate_model),
    candidate_prompt_ref: asString(o.candidate_prompt_ref),
    verdict,
    created_at: asNum(o.created_at),
    duration_ms: asNum(o.duration_ms),
  };
}

export function normalizeReplayRows(raw: unknown): ReplayRow[] {
  return asArray(raw)
    .map(normalizeReplayRow)
    .filter((r): r is ReplayRow => r != null);
}

export function normalizeAgentModelRow(raw: unknown): AgentModelRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const model = asString(o.model);
  if (!model) return null;
  return {
    model,
    session_count: asNum(o.session_count) ?? 0,
    latest_started_at: asNum(o.latest_started_at),
  };
}

export function normalizeAgentModelRows(raw: unknown): AgentModelRow[] {
  return asArray(raw)
    .map(normalizeAgentModelRow)
    .filter((r): r is AgentModelRow => r != null);
}

export type AgentEnvelopeValidation =
  | { ok: true }
  | { ok: false; reason: string };

/** Strict shape check before rendering agent-view twins. */
export function validateAgentEnvelopeShape(raw: unknown): AgentEnvelopeValidation {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return { ok: false, reason: "envelope must be a JSON object" };
  }
  const o = raw as Record<string, unknown>;
  const checks: [string, (v: unknown) => boolean][] = [
    ["view", (v) => typeof v === "string" && v.length > 0],
    ["id", (v) => typeof v === "string"],
    ["generated_at", (v) => typeof v === "string" && v.length > 0],
    ["data", (v) => v !== undefined],
    ["links", (v) => v !== null && typeof v === "object" && !Array.isArray(v)],
    ["hints", (v) => v !== null && typeof v === "object" && !Array.isArray(v)],
  ];
  for (const [key, check] of checks) {
    if (!(key in o)) return { ok: false, reason: `missing field: ${key}` };
    if (!check(o[key])) return { ok: false, reason: `invalid field: ${key}` };
  }
  return { ok: true };
}

export function normalizeAgentEnvelope(raw: unknown): AgentEnvelope {
  const o = asRecord(raw);
  const linksRaw = asRecord(o.links);
  const hintsRaw = asRecord(o.hints);
  const links: Record<string, string | null> = {};
  for (const [k, v] of Object.entries(linksRaw)) {
    links[k] = asString(v);
  }
  const hints: Record<string, string> = {};
  for (const [k, v] of Object.entries(hintsRaw)) {
    const s = asString(v);
    if (s) hints[k] = s;
  }
  return {
    view: asString(o.view) ?? "unknown",
    id: asString(o.id) ?? "",
    generated_at: asString(o.generated_at) ?? "",
    data: o.data ?? null,
    links,
    hints,
  };
}

export function normalizeVersionTimeline(raw: unknown): {
  agent_id: string;
  current_model: string | null;
  versions: AgentVersionRow[];
} {
  const o = asRecord(raw);
  return {
    agent_id: asString(o.agent_id) ?? "",
    current_model: asString(o.current_model),
    versions: normalizeAgentVersionRows(o.versions),
  };
}

export function parseSsePayload(raw: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}
