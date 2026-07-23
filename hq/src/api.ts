import type {
  AgentEnvelope,
  AgentModelRow,
  FleetRow,
  HitlRow,
  SessionRow,
  SignalRow,
  SourceRow,
  ThreatRow,
  Verdict,
} from "./types";

const BASE: string = import.meta.env?.VITE_ARCNET_API ?? "";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json() as Promise<T>;
}

export type PageMeta = {
  total: number;
  limit: number;
  offset: number;
};

export type Paged<T> = { rows: T[] } & PageMeta;

function parseHeaderInt(raw: string | null, fallback: number): number {
  if (raw == null || raw.trim() === "") return fallback;
  const v = Number(raw);
  return Number.isFinite(v) ? v : fallback;
}

function pageMetaFromHeaders(headers: Headers, rowCount: number): PageMeta {
  return {
    total: parseHeaderInt(headers.get("X-Total-Count"), rowCount),
    limit: parseHeaderInt(headers.get("X-Limit"), rowCount),
    offset: parseHeaderInt(headers.get("X-Offset"), 0),
  };
}

/** Fetch JSON and expose response headers (for X-Total-Count pagination). */
async function getJSONPaged<T>(path: string): Promise<{ data: T; headers: Headers }> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return { data: (await res.json()) as T, headers: res.headers };
}

const SESSIONS_PAGE = 500; // server max for /api/sessions

/** Walk /api/sessions pages until X-Total-Count is satisfied. */
async function fetchAllSessions(params?: {
  scenario?: string;
  agent_id?: string;
  model?: string;
  agent_version?: string;
  version_id?: string;
}): Promise<SessionRow[]> {
  const all: SessionRow[] = [];
  let offset = 0;
  let total = Infinity;
  while (offset < total) {
    const q = new URLSearchParams();
    if (params?.scenario) q.set("scenario", params.scenario);
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.model) q.set("model", params.model);
    if (params?.agent_version) q.set("agent_version", params.agent_version);
    if (params?.version_id) q.set("version_id", params.version_id);
    q.set("limit", String(SESSIONS_PAGE));
    q.set("offset", String(offset));
    const { data, headers } = await getJSONPaged<SessionRow[]>(`/api/sessions?${q}`);
    all.push(...data);
    const headerTotal = headers.get("X-Total-Count");
    total = headerTotal != null ? Number(headerTotal) : all.length;
    if (data.length === 0) break;
    offset += data.length;
  }
  return all;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${path} ${detail.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export type ReplayRow = {
  replay_id: string;
  session_id: string;
  candidate_model: string | null;
  candidate_prompt_ref: string | null;
  verdict: Verdict;
  created_at: number | null;
  duration_ms: number | null;
};

export type SignozStatus = {
  signoz_url: string;
  ui_reachable: boolean;
  ui_status: number | string | null;
  api_key_present: boolean;
  query_range_ok: boolean | null;
  query_note: string;
  dashboards?: {
    fleet_ops?: string | null;
    threats_trust?: string | null;
    cost_tokens?: string | null;
    agno?: string | null;
  };
  mcp_note?: string;
};

export type GriffinStatus = {
  estimator: string;
  model?: string;
  status: string;
  series_count?: number;
  ready_count?: number;
  warming_count?: number;
  series_source?: string | null;
  last_anomaly?: {
    series_id?: string;
    agent_id?: string;
    metric?: string;
    z?: number;
    ts_ms?: number;
    fingerprint?: string;
  } | null;
  last_evaluate_ms?: number | null;
  warmth?: Record<string, { status?: string; n?: number; outlier?: boolean }>;
  honesty?: string;
  anomalies?: unknown[];
};

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

export const api = {
  fleet: () => getJSON<FleetRow[]>("/api/fleet"),
  agentModels: (agentId: string) =>
    getJSON<AgentModelRow[]>(`/api/agents/${encodeURIComponent(agentId)}/models`),
  sessions: (params?: {
    scenario?: string;
    agent_id?: string;
    model?: string;
    agent_version?: string;
    version_id?: string;
    limit?: number;
    offset?: number;
    /** When true (default for HQ cascades), page through X-Total-Count. */
    all?: boolean;
  }) => {
    if (params?.all !== false && params?.limit == null && params?.offset == null) {
      return fetchAllSessions({
        scenario: params?.scenario,
        agent_id: params?.agent_id,
        model: params?.model,
        agent_version: params?.agent_version,
        version_id: params?.version_id,
      });
    }
    const q = new URLSearchParams();
    if (params?.scenario) q.set("scenario", params.scenario);
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.model) q.set("model", params.model);
    if (params?.agent_version) q.set("agent_version", params.agent_version);
    if (params?.version_id) q.set("version_id", params.version_id);
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    const qs = q.toString();
    return getJSON<SessionRow[]>(`/api/sessions${qs ? `?${qs}` : ""}`);
  },
  replays: (sessionId?: string) =>
    getJSON<ReplayRow[]>(`/api/replays${sessionId ? `?session_id=${sessionId}` : ""}`),
  signals: (params?: {
    agent_id?: string;
    session_id?: string;
    source?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.session_id) q.set("session_id", params.session_id);
    if (params?.source) q.set("source", params.source);
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    const qs = q.toString();
    return getJSON<SignalRow[]>(`/api/signals${qs ? `?${qs}` : ""}`);
  },
  /** Signals page with X-Total-Count for HQ “showing N of Total”. */
  signalsPage: async (params?: {
    agent_id?: string;
    session_id?: string;
    source?: string;
    limit?: number;
    offset?: number;
  }): Promise<Paged<SignalRow>> => {
    const q = new URLSearchParams();
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.session_id) q.set("session_id", params.session_id);
    if (params?.source) q.set("source", params.source);
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    const qs = q.toString();
    const { data, headers } = await getJSONPaged<SignalRow[]>(
      `/api/signals${qs ? `?${qs}` : ""}`,
    );
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  /** Sessions first page + total (does not walk all pages). */
  sessionsPage: async (params?: {
    scenario?: string;
    agent_id?: string;
    model?: string;
    agent_version?: string;
    version_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<Paged<SessionRow>> => {
    const q = new URLSearchParams();
    if (params?.scenario) q.set("scenario", params.scenario);
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.model) q.set("model", params.model);
    if (params?.agent_version) q.set("agent_version", params.agent_version);
    if (params?.version_id) q.set("version_id", params.version_id);
    q.set("limit", String(params?.limit ?? 100));
    q.set("offset", String(params?.offset ?? 0));
    const { data, headers } = await getJSONPaged<SessionRow[]>(`/api/sessions?${q}`);
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  agentVersions: (agentId: string) =>
    getJSON<AgentVersionRow[]>(`/api/agents/${encodeURIComponent(agentId)}/versions`),
  agentVersionsPage: async (
    agentId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<Paged<AgentVersionRow>> => {
    const q = new URLSearchParams();
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    const qs = q.toString();
    const { data, headers } = await getJSONPaged<AgentVersionRow[]>(
      `/api/agents/${encodeURIComponent(agentId)}/versions${qs ? `?${qs}` : ""}`,
    );
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  agentVersionTimeline: (agentId: string) =>
    getJSON<{ agent_id: string; current_model: string | null; versions: AgentVersionRow[] }>(
      `/api/agents/${encodeURIComponent(agentId)}/versions/timeline`,
    ),
  applyModel: (
    agentId: string,
    body: {
      confirm: true;
      model: string;
      version: string;
      model_version?: string;
      source_ref?: string;
      notes?: string;
      session_id?: string;
      proposal_signal_id?: string;
    },
  ) =>
    postJSON<{
      agent_id: string;
      model: string;
      version: AgentVersionRow;
      proposal: SignalRow | null;
      applied: boolean;
      agentos_reload_required?: boolean;
      agentos_reload_instructions?: string;
      agentos_probe?: {
        probed?: boolean;
        reachable?: boolean;
        sqlite_model?: string;
        live_model?: string | null;
        models_match?: boolean | null;
        note?: string;
      };
    }>(`/api/agents/${encodeURIComponent(agentId)}/apply-model`, body),
  sources: (params?: { agent_id?: string; session_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.session_id) q.set("session_id", params.session_id);
    const qs = q.toString();
    return getJSON<SourceRow[]>(`/api/sources${qs ? `?${qs}` : ""}`);
  },
  threatsPage: async (params?: {
    agent_id?: string;
    since?: number;
    limit?: number;
    offset?: number;
  }): Promise<Paged<ThreatRow>> => {
    const q = new URLSearchParams();
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.since != null) q.set("since", String(params.since));
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    const qs = q.toString();
    const { data, headers } = await getJSONPaged<ThreatRow[]>(
      `/api/threats${qs ? `?${qs}` : ""}`,
    );
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  agentView: (view: string, id: string) =>
    getJSON<AgentEnvelope>(`/api/agent-view/${view}/${encodeURIComponent(id)}`),
  runReplay: (session_id: string, candidate_model: string) =>
    postJSON<Verdict>("/api/replay", { session_id, candidate_model }),
  caseFileUrl: (sessionId: string) => `${BASE}/export/case-file/${sessionId}`,
  signozStatus: () => getJSON<SignozStatus>("/api/signoz/status"),
  griffinStatus: () => getJSON<GriffinStatus>("/api/griffin/status"),
  signozEvidence: (sessionId: string) =>
    getJSON<{
      session_id: string;
      trace_id: string | null;
      links: { signoz_trace: string | null };
      spans: { name: string; duration_ns?: number }[];
      note: string | null;
      mcp_fallback?: string;
    }>(`/api/signoz/evidence?session_id=${encodeURIComponent(sessionId)}`),
  hitlPage: async (params?: {
    session_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<Paged<HitlRow>> => {
    const q = new URLSearchParams();
    if (params?.session_id) q.set("session_id", params.session_id);
    if (params?.status) q.set("status", params.status);
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    const qs = q.toString();
    const { data, headers } = await getJSONPaged<HitlRow[]>(`/api/hitl${qs ? `?${qs}` : ""}`);
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  decideHitl: (hitlId: string, decision: "approved" | "rejected") =>
    postJSON<HitlRow>(`/api/hitl/${encodeURIComponent(hitlId)}`, { decision }),
};

export type BusEvent = {
  event: string;
  data: Record<string, unknown>;
};

/** Subscribe to the SSE signal bus. Returns an unsubscribe function. */
export function subscribeBus(onEvent: (ev: BusEvent) => void): () => void {
  const es = new EventSource(`${BASE}/signals/stream`);
  const forward = (name: string) => (raw: MessageEvent) => {
    try {
      onEvent({ event: name, data: JSON.parse(raw.data as string) });
    } catch {
      // ignore malformed frames
    }
  };
  es.addEventListener("signal", forward("signal"));
  es.addEventListener("replay_progress", forward("replay_progress"));
  es.addEventListener("hitl_request", forward("hitl_request"));
  return () => es.close();
}
