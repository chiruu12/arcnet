import type {
  AgentEnvelope,
  AgentModelRow,
  FleetRow,
  SessionRow,
  SignalRow,
  SourceRow,
  Verdict,
} from "./types";

const BASE: string = import.meta.env.VITE_ARCNET_API ?? "";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json() as Promise<T>;
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
}): Promise<SessionRow[]> {
  const all: SessionRow[] = [];
  let offset = 0;
  let total = Infinity;
  while (offset < total) {
    const q = new URLSearchParams();
    if (params?.scenario) q.set("scenario", params.scenario);
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.model) q.set("model", params.model);
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
      });
    }
    const q = new URLSearchParams();
    if (params?.scenario) q.set("scenario", params.scenario);
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.model) q.set("model", params.model);
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    const qs = q.toString();
    return getJSON<SessionRow[]>(`/api/sessions${qs ? `?${qs}` : ""}`);
  },
  replays: (sessionId?: string) =>
    getJSON<ReplayRow[]>(`/api/replays${sessionId ? `?session_id=${sessionId}` : ""}`),
  signals: (params?: { agent_id?: string; session_id?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.session_id) q.set("session_id", params.session_id);
    if (params?.limit != null) q.set("limit", String(params.limit));
    const qs = q.toString();
    return getJSON<SignalRow[]>(`/api/signals${qs ? `?${qs}` : ""}`);
  },
  agentVersions: (agentId: string) =>
    getJSON<AgentVersionRow[]>(`/api/agents/${encodeURIComponent(agentId)}/versions`),
  agentVersionTimeline: (agentId: string) =>
    getJSON<{ agent_id: string; current_model: string | null; versions: AgentVersionRow[] }>(
      `/api/agents/${encodeURIComponent(agentId)}/versions/timeline`,
    ),
  sources: (params?: { agent_id?: string; session_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.session_id) q.set("session_id", params.session_id);
    const qs = q.toString();
    return getJSON<SourceRow[]>(`/api/sources${qs ? `?${qs}` : ""}`);
  },
  agentView: (view: string, id: string) =>
    getJSON<AgentEnvelope>(`/api/agent-view/${view}/${encodeURIComponent(id)}`),
  runReplay: (session_id: string, candidate_model: string) =>
    postJSON<Verdict>("/api/replay", { session_id, candidate_model }),
  caseFileUrl: (sessionId: string) => `${BASE}/export/case-file/${sessionId}`,
  signozStatus: () => getJSON<SignozStatus>("/api/signoz/status"),
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
  return () => es.close();
}
