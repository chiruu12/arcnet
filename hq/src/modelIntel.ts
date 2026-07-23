/** Parse / format additive GET /api/agents/{id}/models intelligence (docs/27). */

import type {
  AgentModelRow,
  AgentModelsResponse,
  ModelCandidate,
  ReasoningRecommendation,
} from "./types";

function asNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) {
    return Number(v);
  }
  return null;
}

function asRow(raw: unknown): AgentModelRow | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.model !== "string" || !o.model) return null;
  return {
    model: o.model,
    session_count: asNum(o.session_count) ?? 0,
    latest_started_at: asNum(o.latest_started_at),
  };
}

function asCandidate(raw: unknown): ModelCandidate | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.id !== "string" || !o.id) return null;
  return {
    id: o.id,
    provider: typeof o.provider === "string" ? o.provider : "",
    tier: typeof o.tier === "string" ? o.tier : "",
    input_usd_per_mtok: asNum(o.input_usd_per_mtok) ?? 0,
    output_usd_per_mtok: asNum(o.output_usd_per_mtok) ?? 0,
    context_window: asNum(o.context_window) ?? 0,
    reasoning: Boolean(o.reasoning),
    strengths: typeof o.strengths === "string" ? o.strengths : "",
    projected_cost_usd: asNum(o.projected_cost_usd),
    projected_cost_delta: asNum(o.projected_cost_delta),
    price_label: typeof o.price_label === "string" ? o.price_label : "",
    is_current: Boolean(o.is_current),
  };
}

function asReasoning(raw: unknown): ReasoningRecommendation | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.model_id !== "string" || !o.model_id) return null;
  return {
    recommend: Boolean(o.recommend),
    model_id: o.model_id,
    tier: typeof o.tier === "string" ? o.tier : "",
    rationale: typeof o.rationale === "string" ? o.rationale : "",
    evidence:
      o.evidence && typeof o.evidence === "object"
        ? (o.evidence as Record<string, unknown>)
        : {},
    price_label: typeof o.price_label === "string" ? o.price_label : "",
  };
}

/** Accept object payload (docs/27) or legacy bare array. */
export function normalizeAgentModelsResponse(raw: unknown): AgentModelsResponse {
  if (Array.isArray(raw)) {
    const models = raw.map(asRow).filter((r): r is AgentModelRow => r != null);
    return {
      agent_id: "",
      current_model: null,
      catalog_version: "",
      price_label: "",
      models,
      usage_evidence: {
        session_count: 0,
        sessions_with_token_usage: 0,
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0,
      },
      workload_evidence: {
        session_count: 0,
        threat_count: 0,
        threat_rate: 0,
        replay_count: 0,
        verdict_counts: {},
        adversarial_replay_count: 0,
      },
      baseline_projected_cost_usd: null,
      candidates: [],
      reasoning_recommendation: null,
      honesty: "",
    };
  }
  const o = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const modelsRaw = Array.isArray(o.models) ? o.models : [];
  const candRaw = Array.isArray(o.candidates) ? o.candidates : [];
  const ue =
    o.usage_evidence && typeof o.usage_evidence === "object"
      ? (o.usage_evidence as Record<string, unknown>)
      : {};
  const we =
    o.workload_evidence && typeof o.workload_evidence === "object"
      ? (o.workload_evidence as Record<string, unknown>)
      : {};
  return {
    agent_id: typeof o.agent_id === "string" ? o.agent_id : "",
    current_model: typeof o.current_model === "string" ? o.current_model : null,
    catalog_version: typeof o.catalog_version === "string" ? o.catalog_version : "",
    price_label: typeof o.price_label === "string" ? o.price_label : "",
    models: modelsRaw.map(asRow).filter((r): r is AgentModelRow => r != null),
    usage_evidence: {
      session_count: asNum(ue.session_count) ?? 0,
      sessions_with_token_usage: asNum(ue.sessions_with_token_usage) ?? 0,
      input_tokens: asNum(ue.input_tokens) ?? 0,
      output_tokens: asNum(ue.output_tokens) ?? 0,
      total_tokens: asNum(ue.total_tokens) ?? 0,
    },
    workload_evidence: {
      session_count: asNum(we.session_count) ?? 0,
      threat_count: asNum(we.threat_count) ?? 0,
      threat_rate: asNum(we.threat_rate) ?? 0,
      replay_count: asNum(we.replay_count) ?? 0,
      verdict_counts:
        we.verdict_counts && typeof we.verdict_counts === "object"
          ? (we.verdict_counts as Record<string, number>)
          : {},
      adversarial_replay_count: asNum(we.adversarial_replay_count) ?? 0,
    },
    baseline_projected_cost_usd: asNum(o.baseline_projected_cost_usd),
    candidates: candRaw.map(asCandidate).filter((c): c is ModelCandidate => c != null),
    reasoning_recommendation: asReasoning(o.reasoning_recommendation),
    honesty: typeof o.honesty === "string" ? o.honesty : "",
  };
}

/** Format projected USD delta for HQ chrome (null → em dash). */
export function formatCostDelta(delta: number | null | undefined): string {
  if (delta == null || !Number.isFinite(delta)) return "—";
  const abs = Math.abs(delta);
  const body =
    abs >= 1 ? abs.toFixed(2) : abs >= 0.01 ? abs.toFixed(4) : abs.toFixed(6);
  if (delta === 0) return "$0";
  return delta < 0 ? `−$${body}` : `+$${body}`;
}
