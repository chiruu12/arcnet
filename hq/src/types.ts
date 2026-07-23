export type Mode = "human" | "agent";

export type View =
  | "home"
  | "fleet_health"
  | "signals"
  | "hitl"
  | "sources_trust"
  | "time_machine"
  | "case_files"
  | "dashboards"
  | "hq_agent";

export type CascadeLink = {
  agent?: string;
  version?: string;
  session?: string;
  model?: string;
};

export type Health = {
  sessions_24h: number;
  threats_24h: number;
  blocked_24h: number;
  cost_24h_usd: number;
  anomalies_24h: number;
  active_signals: number;
};

export type FleetRow = {
  agent_id: string;
  name: string | null;
  role: string | null;
  exposure: string | null;
  model: string | null;
  last_seen: number | null;
  health: Health;
};

export type SessionRow = {
  session_id: string;
  agent_id: string;
  scenario: string | null;
  goal: string | null;
  model: string | null;
  status: string;
  outcome: Record<string, unknown> | null;
  usage: Record<string, unknown> | null;
  trace_id: string | null;
  agent_version?: string | null;
  started_at: number | null;
  ended_at: number | null;
  has_transcript: number;
};

export type AgentModelRow = {
  model: string;
  session_count: number;
  latest_started_at: number | null;
};

/** Additive model-intelligence payload (docs/27). Cascade list is `models`. */
export type ModelCandidate = {
  id: string;
  provider: string;
  tier: string;
  input_usd_per_mtok: number;
  output_usd_per_mtok: number;
  context_window: number;
  reasoning: boolean;
  strengths: string;
  projected_cost_usd: number | null;
  projected_cost_delta: number | null;
  price_label: string;
  is_current: boolean;
};

export type ReasoningRecommendation = {
  recommend: boolean;
  model_id: string;
  tier: string;
  rationale: string;
  evidence: Record<string, unknown>;
  price_label: string;
};

export type AgentModelsResponse = {
  agent_id: string;
  current_model: string | null;
  catalog_version: string;
  price_label: string;
  models: AgentModelRow[];
  usage_evidence: {
    session_count: number;
    sessions_with_token_usage: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  workload_evidence: {
    session_count: number;
    threat_count: number;
    threat_rate: number;
    replay_count: number;
    verdict_counts: Record<string, number>;
    adversarial_replay_count: number;
  };
  baseline_projected_cost_usd: number | null;
  candidates: ModelCandidate[];
  reasoning_recommendation: ReasoningRecommendation | null;
  honesty: string;
};

export type SignalRow = {
  signal_id: string;
  session_id: string | null;
  agent_id: string;
  kind: string;
  severity: string;
  reason: string;
  guidance: string | null;
  source: string;
  status: string;
  created_at: number | null;
};

export type HitlRow = {
  hitl_id: string;
  run_id: string;
  session_id: string | null;
  payload: Record<string, unknown> | string | null;
  status: string;
  created_at: number | null;
  decided_at: number | null;
};

export type SourceRow = {
  source_id: string;
  session_id: string | null;
  agent_id: string | null;
  origin: string | null;
  trust_level: string | null;
  scan_action: string | null;
  findings: number;
  created_at: number | null;
};

export type ThreatRow = {
  threat_id: string;
  session_id: string | null;
  agent_id: string | null;
  checkpoint: string | null;
  action: string | null;
  category: string | null;
  subcategory: string | null;
  risk_score: number | null;
  trust_level: string | null;
  created_at: number | null;
};

export type Verdict = {
  replay_id: string;
  session_id: string;
  scenario: string | null;
  baseline: Record<string, unknown>;
  candidate: Record<string, unknown>;
  divergences: { step: number; note: string }[];
  verdict: string;
  confidence: string;
  recommendation: string;
};

export type AgentEnvelope = {
  view: string;
  id: string;
  generated_at: string;
  data: unknown;
  links: Record<string, string | null>;
  hints: Record<string, string>;
};
