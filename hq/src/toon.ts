/**
 * Minimal TOON (Token-Oriented Object Notation) encoder for HQ agent_view panels.
 * Tabular arrays use `name[N]{fields}:` headers per https://toonformat.dev/
 */

import type { AgentEnvelope, AgentModelsResponse, ModelCandidate } from "./types";
import type { ModelProposal } from "./proposals";

function isPrimitive(v: unknown): boolean {
  return v == null || typeof v === "boolean" || typeof v === "number" || typeof v === "string";
}

function isUniformObjectArray(rows: unknown[]): rows is Record<string, unknown>[] {
  if (rows.length === 0 || !rows.every((r) => r && typeof r === "object" && !Array.isArray(r))) {
    return false;
  }
  const keys = rows.map((r) => Object.keys(r as Record<string, unknown>).sort().join("|"));
  return new Set(keys).size === 1 && keys[0] !== "";
}

function escCell(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function tabularRows(
  name: string,
  fields: string[],
  rows: Record<string, unknown>[],
): string {
  if (rows.length === 0) return `${name}[0]{${fields.join(",")}}:`;
  const lines = [`${name}[${rows.length}]{${fields.join(",")}}:`];
  for (const row of rows) {
    lines.push(`  ${fields.map((f) => escCell(row[f])).join(",")}`);
  }
  return lines.join("\n");
}

/** Generic JSON-compatible value → TOON text. */
export function encodeToon(value: unknown, indent = 0): string {
  const pad = "  ".repeat(indent);
  if (value == null) return "";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") {
    if (value.includes("\n") || value.includes(":") || value.includes(",")) {
      return `"${value.replace(/"/g, '""')}"`;
    }
    return value;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return `${pad}[]`;
    if (isUniformObjectArray(value)) {
      const fields = Object.keys(value[0] as Record<string, unknown>);
      return tabularRows(indent === 0 ? "rows" : "items", fields, value);
    }
    if (value.every(isPrimitive)) {
      return `${pad}${value.map((v) => escCell(v)).join(",")}`;
    }
    return value
      .map((item, i) => `${pad}- [${i}]\n${encodeToon(item, indent + 1)}`)
      .join("\n");
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const lines: string[] = [];
    for (const [key, val] of Object.entries(obj)) {
      if (val == null) continue;
      if (isPrimitive(val)) {
        lines.push(`${pad}${key}: ${encodeToon(val, 0)}`);
      } else if (Array.isArray(val) && isUniformObjectArray(val)) {
        const fields = Object.keys(val[0] as Record<string, unknown>);
        lines.push(tabularRows(key, fields, val));
      } else if (Array.isArray(val) && val.every(isPrimitive)) {
        lines.push(`${pad}${key}[${val.length}]: ${val.map((v) => escCell(v)).join(",")}`);
      } else {
        lines.push(`${pad}${key}:`);
        lines.push(encodeToon(val, indent + 1));
      }
    }
    return lines.join("\n");
  }
  return escCell(value);
}

/** Encode standard GET /api/agent-view envelope as TOON. */
export function envelopeToToon(env: AgentEnvelope): string {
  return [
    `view: ${env.view}`,
    `id: ${env.id}`,
    `generated_at: ${env.generated_at}`,
    "links:",
    encodeToon(env.links, 1),
    "hints:",
    encodeToon(env.hints, 1),
    "data:",
    encodeToon(env.data, 1),
  ].join("\n");
}

function candidateRow(c: ModelCandidate): Record<string, unknown> {
  return {
    id: c.id,
    bucket: c.bucket ?? "",
    tier: c.capability_tier || c.tier,
    cost: c.cost_class,
    in: c.input_usd_per_mtok,
    cached: c.cached_input_usd_per_mtok,
    out: c.output_usd_per_mtok,
    ctx: c.context_window,
    delta: c.projected_cost_delta,
    status: c.status,
    current: c.is_current ? 1 : 0,
  };
}

function flattenCandidates(intel: AgentModelsResponse): ModelCandidate[] {
  const buckets = intel.recommendation_buckets;
  if (buckets) {
    return [
      ...buckets.recommended_upgrade,
      ...buckets.cost_saver,
      ...buckets.peer,
      ...buckets.not_advised,
      ...intel.candidates.filter((c) => c.is_current),
    ];
  }
  return intel.candidates;
}

/** Encode model intelligence payload as TOON for agent_view. */
export function modelIntelToToon(intel: AgentModelsResponse): string {
  const ue = intel.usage_evidence;
  const we = intel.workload_evidence;
  const meta = [
    "meta:",
    `  agent_id: ${intel.agent_id}`,
    `  current_model: ${intel.current_model ?? ""}`,
    `  catalog_version: ${intel.catalog_version}`,
    `  price_label: ${intel.price_label}`,
    `  baseline_cost_usd: ${intel.baseline_projected_cost_usd ?? ""}`,
    "usage_evidence:",
    `  sessions: ${ue.session_count}`,
    `  tokens: ${ue.total_tokens}`,
    "workload_evidence:",
    `  threat_rate: ${we.threat_rate}`,
    `  replay_count: ${we.replay_count}`,
  ];
  const rr = intel.reasoning_recommendation;
  if (rr) {
    meta.push(
      "reasoning_rec:",
      `  model_id: ${rr.model_id}`,
      `  recommend: ${rr.recommend ? 1 : 0}`,
      `  summary: ${rr.summary ?? rr.rationale ?? ""}`,
    );
  }
  const fields = [
    "id",
    "bucket",
    "tier",
    "cost",
    "in",
    "cached",
    "out",
    "ctx",
    "delta",
    "status",
    "current",
  ];
  const highlights = (intel.catalog_highlights ?? []).map(candidateRow);
  const rows = flattenCandidates(intel).map(candidateRow);
  const parts = [...meta, ""];
  if (highlights.length > 0) {
    parts.push(tabularRows("catalog_highlights", fields, highlights), "");
  }
  parts.push(tabularRows("candidates", fields, rows));
  return parts.join("\n");
}

/** Encode model proposals as TOON for agent_view. */
export function proposalsToToon(proposals: ModelProposal[]): string {
  const fields = [
    "signal_id",
    "status",
    "from_model",
    "to_model",
    "task_type",
    "reason",
    "evidence_count",
  ];
  const rows = proposals.map((p) => ({
    signal_id: p.signal_id,
    status: p.status,
    from_model: p.from_model ?? "",
    to_model: p.to_model ?? "",
    task_type: p.task_type ?? "",
    reason: p.reason.slice(0, 120),
    evidence_count: p.evidence_refs.length,
  }));
  const body = tabularRows("proposals", fields, rows);
  if (proposals.length === 0) return body;
  const evidenceLines = proposals.flatMap((p) =>
    p.evidence_refs.length > 0
      ? [`evidence[${p.signal_id}]: ${p.evidence_refs.join(",")}`]
      : [],
  );
  return evidenceLines.length > 0 ? `${body}\n\n${evidenceLines.join("\n")}` : body;
}

/** Rough token estimate for UI badge (chars / 4 heuristic). */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

export function toonVsJsonSavings(toon: string, json: string): number | null {
  const t = estimateTokens(toon);
  const j = estimateTokens(json);
  if (j === 0) return null;
  return Math.round((1 - t / j) * 100);
}
