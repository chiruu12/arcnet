/** Parse / format additive GET /api/agents/{id}/models intelligence (docs/27). */

import type {
  AgentModelRow,
  AgentModelsResponse,
  ModelCandidate,
  ModelFit,
  ReasoningRecommendation,
  RecommendationBuckets,
} from "./types";

function asNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) {
    return Number(v);
  }
  return null;
}

function asStrArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
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

function asFit(raw: unknown): ModelFit | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const o = raw as Record<string, unknown>;
  return {
    score: asNum(o.score) ?? 0,
    reasons: asStrArray(o.reasons),
    blockers: asStrArray(o.blockers),
  };
}

function asCandidate(raw: unknown): ModelCandidate | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.id !== "string" || !o.id) return null;
  const cap = typeof o.capability_tier === "string" ? o.capability_tier : "";
  const tier = typeof o.tier === "string" ? o.tier : cap;
  return {
    id: o.id,
    provider: typeof o.provider === "string" ? o.provider : "",
    display_name: typeof o.display_name === "string" ? o.display_name : o.id,
    capability_tier: cap,
    cost_class: typeof o.cost_class === "string" ? o.cost_class : "",
    tier,
    status: typeof o.status === "string" ? o.status : "current",
    input_usd_per_mtok: asNum(o.input_usd_per_mtok) ?? 0,
    cached_input_usd_per_mtok: asNum(o.cached_input_usd_per_mtok) ?? 0,
    output_usd_per_mtok: asNum(o.output_usd_per_mtok) ?? 0,
    context_window: asNum(o.context_window) ?? 0,
    max_output_tokens: asNum(o.max_output_tokens),
    reasoning: Boolean(o.reasoning),
    reasoning_control: typeof o.reasoning_control === "string" ? o.reasoning_control : undefined,
    strengths: typeof o.strengths === "string" ? o.strengths : "",
    caveats: asStrArray(o.caveats),
    price_verified: typeof o.price_verified === "string" ? o.price_verified : null,
    projected_cost_usd: asNum(o.projected_cost_usd),
    projected_cost_usd_cached: asNum(o.projected_cost_usd_cached),
    projected_cost_delta: asNum(o.projected_cost_delta),
    price_label: typeof o.price_label === "string" ? o.price_label : "",
    is_current: Boolean(o.is_current),
    bucket: typeof o.bucket === "string" ? o.bucket : undefined,
    fit: asFit(o.fit),
  };
}

function asReasoning(raw: unknown): ReasoningRecommendation | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.model_id !== "string" || !o.model_id) return null;
  const evidence = o.evidence;
  return {
    recommend: Boolean(o.recommend),
    model_id: o.model_id,
    capability_tier:
      typeof o.capability_tier === "string" ? o.capability_tier : undefined,
    tier: typeof o.tier === "string" ? o.tier : "",
    summary: typeof o.summary === "string" ? o.summary : undefined,
    rationale: typeof o.rationale === "string" ? o.rationale : undefined,
    evidence:
      Array.isArray(evidence) || (evidence && typeof evidence === "object")
        ? (evidence as Record<string, unknown> | unknown[])
        : {},
    price_label: typeof o.price_label === "string" ? o.price_label : "",
  };
}

function asBuckets(raw: unknown, candidates: ModelCandidate[]): RecommendationBuckets {
  const empty = (): RecommendationBuckets => ({
    recommended_upgrade: [],
    cost_saver: [],
    peer: [],
    not_advised: [],
  });
  if (!raw || typeof raw !== "object") {
    const out = empty();
    for (const c of candidates) {
      if (c.is_current) continue;
      const b = c.bucket ?? "not_advised";
      out[b as keyof RecommendationBuckets]?.push(c);
    }
    return out;
  }
  const o = raw as Record<string, unknown>;
  const parseList = (k: keyof RecommendationBuckets) =>
    (Array.isArray(o[k]) ? o[k] : [])
      .map(asCandidate)
      .filter((c): c is ModelCandidate => c != null);
  return {
    recommended_upgrade: parseList("recommended_upgrade"),
    cost_saver: parseList("cost_saver"),
    peer: parseList("peer"),
    not_advised: parseList("not_advised"),
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
      catalog_highlights: [],
      reasoning_recommendation: null,
      honesty: "",
    };
  }
  const o = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const modelsRaw = Array.isArray(o.models) ? o.models : [];
  const candRaw = Array.isArray(o.candidates) ? o.candidates : [];
  const candidates = candRaw.map(asCandidate).filter((c): c is ModelCandidate => c != null);
  const hiRaw = Array.isArray(o.catalog_highlights) ? o.catalog_highlights : [];
  const catalog_highlights = hiRaw
    .map(asCandidate)
    .filter((c): c is ModelCandidate => c != null);
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
    baseline_projected_cost_usd_cached: asNum(o.baseline_projected_cost_usd_cached),
    candidates,
    catalog_highlights,
    recommendation_buckets: asBuckets(o.recommendation_buckets, candidates),
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

export function formatPricePerMtok(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  if (v === 0) return "—";
  return v >= 1 ? `$${v.toFixed(2)}` : `$${v.toFixed(3)}`;
}

const BUCKET_LABELS: Record<string, string> = {
  recommended_upgrade: "recommended upgrade",
  cost_saver: "cost saver",
  peer: "peer",
  not_advised: "not advised",
};

export function bucketLabel(bucket: string): string {
  return BUCKET_LABELS[bucket] ?? bucket;
}
