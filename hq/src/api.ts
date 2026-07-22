import type {
  AgentEnvelope,
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
};

export const api = {
  fleet: () => getJSON<FleetRow[]>("/api/fleet"),
  sessions: (params?: { scenario?: string; agent_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.scenario) q.set("scenario", params.scenario);
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    const qs = q.toString();
    return getJSON<SessionRow[]>(`/api/sessions${qs ? `?${qs}` : ""}`);
  },
  replays: (sessionId?: string) =>
    getJSON<ReplayRow[]>(`/api/replays${sessionId ? `?session_id=${sessionId}` : ""}`),
  signals: () => getJSON<SignalRow[]>("/api/signals"),
  sources: () => getJSON<SourceRow[]>("/api/sources"),
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
