import type {
  AgentEnvelope,
  AgentModelsResponse,
  HitlRow,
  SessionRow,
  SignalRow,
  ThreatRow,
} from "./types";
import { normalizeAgentModelsResponse } from "./modelIntel.ts";
import {
  ApiError,
  formatApiErrorMessage,
  normalizeAgentEnvelope,
  normalizeAgentModelRows,
  normalizeAgentVersionRows,
  normalizeFleetRows,
  normalizeHitlRows,
  normalizeReplayRows,
  normalizeSessionRows,
  normalizeSignalRows,
  normalizeSourceRows,
  normalizeThreatRows,
  normalizeVerdict,
  normalizeVersionTimeline,
  parseSsePayload,
  readJsonBody,
  validateAgentEnvelopeShape,
  type AgentVersionRow,
  type ReplayRow,
} from "./apiResilience.ts";

export type { AgentVersionRow, ReplayRow };

const BASE: string = import.meta.env?.VITE_ARCNET_API ?? "";

async function requestJSON(path: string, init?: RequestInit): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError({
      message: "arcnet-server unreachable — start uvicorn on :8000 and reload",
      offline: true,
      path,
    });
  }
  const body = await readJsonBody(res).catch((e: unknown) => {
    if (e instanceof ApiError) throw e;
    throw new ApiError({
      message: String(e),
      status: res.status,
      path,
    });
  });
  if (!res.ok) {
    const text =
      body && typeof body === "object"
        ? JSON.stringify(body)
        : String(body ?? "");
    throw new ApiError({
      message: formatApiErrorMessage(res.status, path, text, res.statusText),
      status: res.status,
      path,
    });
  }
  return body;
}

async function getJSON<T>(path: string, normalize: (raw: unknown) => T): Promise<T> {
  const body = await requestJSON(path);
  return normalize(body);
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
async function getJSONPaged<T>(
  path: string,
  normalizeRows: (raw: unknown) => T[],
): Promise<{ data: T[]; headers: Headers }> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`);
  } catch {
    throw new ApiError({
      message: "arcnet-server unreachable — start uvicorn on :8000 and reload",
      offline: true,
      path,
    });
  }
  const body = await readJsonBody(res).catch((e: unknown) => {
    if (e instanceof ApiError) throw e;
    throw new ApiError({
      message: String(e),
      status: res.status,
      path,
    });
  });
  if (!res.ok) {
    const text =
      body && typeof body === "object"
        ? JSON.stringify(body)
        : String(body ?? "");
    throw new ApiError({
      message: formatApiErrorMessage(res.status, path, text, res.statusText),
      status: res.status,
      path,
    });
  }
  return { data: normalizeRows(body), headers: res.headers };
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
    const { data, headers } = await getJSONPaged<SessionRow>(
      `/api/sessions?${q}`,
      normalizeSessionRows,
    );
    all.push(...data);
    const headerTotal = headers.get("X-Total-Count");
    total = headerTotal != null ? Number(headerTotal) : all.length;
    if (!Number.isFinite(total)) total = all.length;
    if (data.length === 0) break;
    offset += data.length;
  }
  return all;
}

async function postJSON<T>(path: string, body: unknown, normalize: (raw: unknown) => T): Promise<T> {
  const parsed = await requestJSON(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return normalize(parsed);
}

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

function normalizeSignozStatus(raw: unknown): SignozStatus {
  const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const dashboardsRaw =
    o.dashboards && typeof o.dashboards === "object"
      ? (o.dashboards as Record<string, unknown>)
      : {};
  return {
    signoz_url: typeof o.signoz_url === "string" ? o.signoz_url : "",
    ui_reachable: Boolean(o.ui_reachable),
    ui_status:
      typeof o.ui_status === "number" || typeof o.ui_status === "string" ? o.ui_status : null,
    api_key_present: Boolean(o.api_key_present),
    query_range_ok:
      typeof o.query_range_ok === "boolean" ? o.query_range_ok : o.query_range_ok == null ? null : false,
    query_note: typeof o.query_note === "string" ? o.query_note : "",
    dashboards: {
      fleet_ops:
        typeof dashboardsRaw.fleet_ops === "string" ? dashboardsRaw.fleet_ops : null,
      threats_trust:
        typeof dashboardsRaw.threats_trust === "string" ? dashboardsRaw.threats_trust : null,
      cost_tokens:
        typeof dashboardsRaw.cost_tokens === "string" ? dashboardsRaw.cost_tokens : null,
      agno: typeof dashboardsRaw.agno === "string" ? dashboardsRaw.agno : null,
    },
    mcp_note: typeof o.mcp_note === "string" ? o.mcp_note : undefined,
  };
}

function normalizeGriffinStatus(raw: unknown): GriffinStatus {
  const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    estimator: typeof o.estimator === "string" ? o.estimator : "MAD",
    model: typeof o.model === "string" ? o.model : undefined,
    status: typeof o.status === "string" ? o.status : "unknown",
    series_count: typeof o.series_count === "number" ? o.series_count : undefined,
    ready_count: typeof o.ready_count === "number" ? o.ready_count : undefined,
    warming_count: typeof o.warming_count === "number" ? o.warming_count : undefined,
    series_source: typeof o.series_source === "string" ? o.series_source : null,
    last_anomaly:
      o.last_anomaly && typeof o.last_anomaly === "object"
        ? (o.last_anomaly as GriffinStatus["last_anomaly"])
        : null,
    last_evaluate_ms: typeof o.last_evaluate_ms === "number" ? o.last_evaluate_ms : null,
    warmth:
      o.warmth && typeof o.warmth === "object"
        ? (o.warmth as GriffinStatus["warmth"])
        : undefined,
    honesty: typeof o.honesty === "string" ? o.honesty : undefined,
    anomalies: Array.isArray(o.anomalies) ? o.anomalies : [],
  };
}

export const api = {
  fleet: () => getJSON("/api/fleet", normalizeFleetRows),
  agentModels: (agentId: string) =>
    getJSON(`/api/agents/${encodeURIComponent(agentId)}/models`, normalizeAgentModelRows),
  agentModelsIntel: async (agentId: string): Promise<AgentModelsResponse> => {
    const raw = await requestJSON(`/api/agents/${encodeURIComponent(agentId)}/model-intel`);
    return normalizeAgentModelsResponse(raw);
  },
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
    return getJSON(`/api/sessions${qs ? `?${qs}` : ""}`, normalizeSessionRows);
  },
  replays: (sessionId?: string) =>
    getJSON(
      `/api/replays${sessionId ? `?session_id=${sessionId}` : ""}`,
      normalizeReplayRows,
    ),
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
    return getJSON(`/api/signals${qs ? `?${qs}` : ""}`, normalizeSignalRows);
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
    const { data, headers } = await getJSONPaged<SignalRow>(
      `/api/signals${qs ? `?${qs}` : ""}`,
      normalizeSignalRows,
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
    const { data, headers } = await getJSONPaged<SessionRow>(
      `/api/sessions?${q}`,
      normalizeSessionRows,
    );
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  agentVersions: (agentId: string) =>
    getJSON(
      `/api/agents/${encodeURIComponent(agentId)}/versions`,
      normalizeAgentVersionRows,
    ),
  agentVersionsPage: async (
    agentId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<Paged<AgentVersionRow>> => {
    const q = new URLSearchParams();
    if (params?.limit != null) q.set("limit", String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    const qs = q.toString();
    const { data, headers } = await getJSONPaged<AgentVersionRow>(
      `/api/agents/${encodeURIComponent(agentId)}/versions${qs ? `?${qs}` : ""}`,
      normalizeAgentVersionRows,
    );
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  agentVersionTimeline: (agentId: string) =>
    getJSON(
      `/api/agents/${encodeURIComponent(agentId)}/versions/timeline`,
      normalizeVersionTimeline,
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
    postJSON(`/api/agents/${encodeURIComponent(agentId)}/apply-model`, body, (raw) => {
      const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
      const version = normalizeAgentVersionRows([o.version])[0];
      if (!version) {
        throw new ApiError({
          message: "apply-model returned malformed version row",
          path: `/api/agents/${agentId}/apply-model`,
        });
      }
      return {
        agent_id: typeof o.agent_id === "string" ? o.agent_id : agentId,
        model: typeof o.model === "string" ? o.model : body.model,
        version,
        proposal: normalizeSignalRows([o.proposal])[0] ?? null,
        applied: Boolean(o.applied),
        agentos_reload_required:
          typeof o.agentos_reload_required === "boolean" ? o.agentos_reload_required : undefined,
        agentos_reload_instructions:
          typeof o.agentos_reload_instructions === "string"
            ? o.agentos_reload_instructions
            : undefined,
        agentos_probe:
          o.agentos_probe && typeof o.agentos_probe === "object"
            ? (o.agentos_probe as {
                probed?: boolean;
                reachable?: boolean;
                sqlite_model?: string;
                live_model?: string | null;
                models_match?: boolean | null;
                note?: string;
              })
            : undefined,
      };
    }),
  sources: (params?: { agent_id?: string; session_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.agent_id) q.set("agent_id", params.agent_id);
    if (params?.session_id) q.set("session_id", params.session_id);
    const qs = q.toString();
    return getJSON(`/api/sources${qs ? `?${qs}` : ""}`, normalizeSourceRows);
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
    const { data, headers } = await getJSONPaged<ThreatRow>(
      `/api/threats${qs ? `?${qs}` : ""}`,
      normalizeThreatRows,
    );
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  agentView: async (view: string, id: string): Promise<AgentEnvelope> => {
    const path = `/api/agent-view/${view}/${encodeURIComponent(id)}`;
    const body = await requestJSON(path);
    const validation = validateAgentEnvelopeShape(body);
    if (!validation.ok) {
      throw new ApiError({
        message: `agent-view envelope invalid — ${validation.reason}`,
        path,
      });
    }
    return normalizeAgentEnvelope(body);
  },
  runReplay: (
    session_id: string,
    candidate: { candidate_model?: string; candidate_prompt?: string },
  ) =>
    postJSON("/api/replay", { session_id, ...candidate }, (raw) => {
      const verdict = normalizeVerdict(raw);
      if (!verdict) {
        throw new ApiError({
          message: "replay returned malformed verdict",
          path: "/api/replay",
        });
      }
      return verdict;
    }),
  caseFileUrl: (sessionId: string) => `${BASE}/export/case-file/${sessionId}`,
  signozStatus: () => getJSON("/api/signoz/status", normalizeSignozStatus),
  griffinStatus: () => getJSON("/api/griffin/status", normalizeGriffinStatus),
  signozEvidence: (sessionId: string) =>
    getJSON(`/api/signoz/evidence?session_id=${encodeURIComponent(sessionId)}`, (raw) => {
      const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
      const spans = Array.isArray(o.spans) ? o.spans : [];
      return {
        session_id: typeof o.session_id === "string" ? o.session_id : sessionId,
        trace_id: typeof o.trace_id === "string" ? o.trace_id : null,
        links: {
          signoz_trace:
            o.links &&
            typeof o.links === "object" &&
            typeof (o.links as Record<string, unknown>).signoz_trace === "string"
              ? ((o.links as Record<string, unknown>).signoz_trace as string)
              : null,
        },
        spans: spans
          .filter((s) => s && typeof s === "object")
          .map((s) => {
            const row = s as Record<string, unknown>;
            return {
              name: typeof row.name === "string" ? row.name : "—",
              duration_ns: typeof row.duration_ns === "number" ? row.duration_ns : undefined,
            };
          }),
        note: typeof o.note === "string" ? o.note : null,
        mcp_fallback: typeof o.mcp_fallback === "string" ? o.mcp_fallback : undefined,
      };
    }),
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
    const { data, headers } = await getJSONPaged<HitlRow>(
      `/api/hitl${qs ? `?${qs}` : ""}`,
      normalizeHitlRows,
    );
    return { rows: data, ...pageMetaFromHeaders(headers, data.length) };
  },
  decideHitl: (hitlId: string, decision: "approved" | "rejected") =>
    postJSON(`/api/hitl/${encodeURIComponent(hitlId)}`, { decision }, (raw) => {
      const row = normalizeHitlRows([raw])[0];
      if (!row) {
        throw new ApiError({
          message: "HITL decide returned malformed row",
          path: `/api/hitl/${hitlId}`,
        });
      }
      return row;
    }),
};

export type BusEvent = {
  event: string;
  data: Record<string, unknown>;
};

/** SSE connection state — same idiom as shell breadcrumb (connecting / live / api_down). */
export type StreamStatus = "connecting" | "live" | "api_down";

/** Subscribe to the SSE signal bus. Returns an unsubscribe function. */
export function subscribeBus(
  onEvent: (ev: BusEvent) => void,
  onStatus?: (status: StreamStatus) => void,
): () => void {
  let es: EventSource | null = null;
  try {
    es = new EventSource(`${BASE}/signals/stream`);
  } catch {
    onStatus?.("api_down");
    return () => {};
  }
  onStatus?.("connecting");
  const forward = (name: string) => (raw: MessageEvent) => {
    const data = parseSsePayload(String(raw.data ?? ""));
    if (!data) return;
    onEvent({ event: name, data });
  };
  es.addEventListener("signal", forward("signal"));
  es.addEventListener("replay_progress", forward("replay_progress"));
  es.addEventListener("hitl_request", forward("hitl_request"));
  es.onopen = () => onStatus?.("live");
  es.onerror = () => {
    onStatus?.("api_down");
    /* EventSource reconnects; must not throw */
  };
  return () => {
    es?.close();
  };
}

/** Download a case-file zip with visible error surfacing (no silent anchor failures). */
export async function downloadCaseFile(sessionId: string): Promise<void> {
  const path = `/export/case-file/${encodeURIComponent(sessionId)}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`);
  } catch {
    throw new ApiError({
      message: "arcnet-server unreachable — start uvicorn on :8000 and reload",
      offline: true,
      path,
    });
  }
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError({
      message: formatApiErrorMessage(res.status, path, text, res.statusText),
      status: res.status,
      path,
    });
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `case-file-${sessionId}.zip`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export { ApiError, isOfflineError, toUserError } from "./apiResilience.ts";
