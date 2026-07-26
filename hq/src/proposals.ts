/** Parse hq_agent model-change proposal signals into structured rows. */

import type { SignalRow } from "./types";

export type ModelProposal = {
  signal_id: string;
  agent_id: string;
  session_id: string | null;
  status: string;
  created_at: number | null;
  reason: string;
  from_model: string | null;
  to_model: string | null;
  task_type: string | null;
  evidence_refs: string[];
  guidance: string | null;
};

function parseArrow(guidance: string | null): { from: string | null; to: string | null } {
  if (!guidance) return { from: null, to: null };
  const arrow = guidance.match(
    /:\s*([A-Za-z0-9._-]+)\s*→\s*([A-Za-z0-9._-]+)/,
  );
  if (arrow) {
    return {
      from: arrow[1]?.replace(/\.$/, "") ?? null,
      to: arrow[2]?.replace(/\.$/, "") ?? null,
    };
  }
  const tail = guidance.match(/→\s*([A-Za-z0-9._-]+)/);
  if (tail) return { from: null, to: tail[1]?.replace(/\.$/, "") ?? null };
  return { from: null, to: null };
}

function parseTaskType(guidance: string | null): string | null {
  if (!guidance) return null;
  const m = guidance.match(/task_type=([A-Za-z0-9._-]+)/);
  return m?.[1]?.replace(/\.$/, "") ?? null;
}

function parseEvidenceRefs(guidance: string | null): string[] {
  if (!guidance) return [];
  const m = guidance.match(/evidence_refs=([^.\n]+)/);
  if (!m?.[1]) return [];
  return m[1]
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 12);
}

export function parseModelProposal(row: SignalRow): ModelProposal {
  const { from, to } = parseArrow(row.guidance);
  return {
    signal_id: row.signal_id,
    agent_id: row.agent_id,
    session_id: row.session_id,
    status: row.status,
    created_at: row.created_at,
    reason: row.reason,
    from_model: from,
    to_model: to,
    task_type: parseTaskType(row.guidance),
    evidence_refs: parseEvidenceRefs(row.guidance),
    guidance: row.guidance,
  };
}

export function parseModelProposals(rows: SignalRow[]): ModelProposal[] {
  return rows.map(parseModelProposal);
}

export function proposalStatusClass(status: string): string {
  if (status === "applied") return "ok";
  if (status === "open" || status === "active") return "warn";
  return "";
}
