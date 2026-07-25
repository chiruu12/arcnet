import type { SourceRow } from "./types";

/** Threat row from GET /api/agent-view/threats/{session_id} — includes evidence for provenance. */
export type AgentThreatRow = {
  threat_id: string;
  session_id?: string | null;
  agent_id?: string | null;
  checkpoint?: string | null;
  action?: string | null;
  category?: string | null;
  subcategory?: string | null;
  risk_score?: number | null;
  trust_level?: string | null;
  evidence_excerpt?: string | null;
  created_at?: number | null;
};

export type IngestStep = {
  index: number;
  source: SourceRow;
  linkedThreats: AgentThreatRow[];
};

export type IngestSummary = {
  sourceCount: number;
  threatCount: number;
  ingestClean: boolean;
  downstreamBlock: AgentThreatRow | null;
  narrative: string;
  provenanceLinkCount: number;
};

const INGEST_CHECKPOINT = "retrieved";

/** Oldest-first ingest order (API returns newest-first). */
export function sortSourcesIngestOrder(sources: SourceRow[]): SourceRow[] {
  return [...sources].sort((a, b) => {
    const ta = a.created_at ?? 0;
    const tb = b.created_at ?? 0;
    if (ta !== tb) return ta - tb;
    return (a.source_id ?? "").localeCompare(b.source_id ?? "");
  });
}

function evidenceMentionsOrigin(evidence: string, origin: string): boolean {
  if (!origin.trim()) return false;
  const ev = evidence.toLowerCase();
  const o = origin.toLowerCase();
  if (ev.includes(`'${o}'`) || ev.includes(`"${o}"`)) return true;
  return ev.includes(o);
}

/** Link downstream threats whose provenance points at this ingested source. */
export function threatsLinkedToSource(
  source: SourceRow,
  threats: AgentThreatRow[],
): AgentThreatRow[] {
  const origin = source.origin ?? "";
  const trust = source.trust_level ?? "";
  return threats.filter((t) => {
    const ev = t.evidence_excerpt ?? "";
    if (t.subcategory === "retrieved_source_in_side_effect" && trust === "retrieved") {
      return evidenceMentionsOrigin(ev, origin);
    }
    if (t.category === "taint" && trust === "retrieved" && origin) {
      return evidenceMentionsOrigin(ev, origin);
    }
    return false;
  });
}

export function buildIngestTimeline(
  sources: SourceRow[],
  threats: AgentThreatRow[],
): IngestStep[] {
  const ordered = sortSourcesIngestOrder(sources);
  return ordered.map((source, index) => ({
    index: index + 1,
    source,
    linkedThreats: threatsLinkedToSource(source, threats),
  }));
}

export function ingestSummary(
  sources: SourceRow[],
  threats: AgentThreatRow[],
): IngestSummary {
  const ordered = sortSourcesIngestOrder(sources);
  const ingestClean = ordered.every(
    (s) => (s.scan_action ?? "allow") === "allow" && (s.findings ?? 0) === 0,
  );
  const downstream = threats
    .filter((t) => t.checkpoint !== INGEST_CHECKPOINT)
    .sort((a, b) => {
      const pa = actionPriority(a.action);
      const pb = actionPriority(b.action);
      if (pa !== pb) return pb - pa;
      return (b.risk_score ?? 0) - (a.risk_score ?? 0);
    });
  const linkedIds = new Set(
    buildIngestTimeline(sources, threats).flatMap((s) =>
      s.linkedThreats.map((t) => t.threat_id),
    ),
  );
  const provenanceBlock = downstream.find(
    (t) => linkedIds.has(t.threat_id) && t.action === "block",
  );
  const downstreamBlock =
    provenanceBlock ??
    downstream.find((t) => t.action === "block") ??
    downstream[0] ??
    null;

  const linked = buildIngestTimeline(sources, threats).flatMap((s) => s.linkedThreats);
  const uniqueLinked = [...new Map(linked.map((t) => [t.threat_id, t])).values()];

  let narrative = "no ingested sources for this session";
  if (ordered.length > 0) {
    if (ingestClean && downstreamBlock) {
      narrative = `clean at ingest · blocked at ${downstreamBlock.checkpoint ?? "downstream"}`;
    } else if (ingestClean && threats.length === 0) {
      narrative = "clean at ingest · no downstream threats";
    } else if (!ingestClean) {
      narrative = "guard flagged content during ingest";
    } else {
      narrative = "ingest complete · review downstream guard actions";
    }
  }

  return {
    sourceCount: ordered.length,
    threatCount: threats.length,
    ingestClean,
    downstreamBlock,
    narrative,
    provenanceLinkCount: uniqueLinked.length,
  };
}

function actionPriority(action: string | null | undefined): number {
  switch (action) {
    case "block":
      return 3;
    case "redact":
      return 2;
    case "review":
      return 1;
    default:
      return 0;
  }
}

/** Threats not tied to any ingested source (trajectory, output-only, etc.). */
export function unlinkedThreats(
  sources: SourceRow[],
  threats: AgentThreatRow[],
): AgentThreatRow[] {
  const linkedIds = new Set(
    buildIngestTimeline(sources, threats).flatMap((s) =>
      s.linkedThreats.map((t) => t.threat_id),
    ),
  );
  return threats.filter((t) => !linkedIds.has(t.threat_id));
}

export function parseAgentThreats(data: unknown): AgentThreatRow[] {
  if (!data || typeof data !== "object") return [];
  const o = data as Record<string, unknown>;
  const rows = Array.isArray(o.threats) ? o.threats : [];
  return rows
    .filter((r) => r && typeof r === "object")
    .map((r) => {
      const row = r as Record<string, unknown>;
      return {
        threat_id: String(row.threat_id ?? ""),
        session_id: typeof row.session_id === "string" ? row.session_id : null,
        agent_id: typeof row.agent_id === "string" ? row.agent_id : null,
        checkpoint: typeof row.checkpoint === "string" ? row.checkpoint : null,
        action: typeof row.action === "string" ? row.action : null,
        category: typeof row.category === "string" ? row.category : null,
        subcategory: typeof row.subcategory === "string" ? row.subcategory : null,
        risk_score: typeof row.risk_score === "number" ? row.risk_score : null,
        trust_level: typeof row.trust_level === "string" ? row.trust_level : null,
        evidence_excerpt:
          typeof row.evidence_excerpt === "string" ? row.evidence_excerpt : null,
        created_at: typeof row.created_at === "number" ? row.created_at : null,
      };
    })
    .filter((t) => t.threat_id);
}

export function buildContextInspectorTwin(
  sessionId: string,
  sources: SourceRow[],
  threats: AgentThreatRow[],
  links: Record<string, string | null> = {},
) {
  const timeline = buildIngestTimeline(sources, threats);
  const summary = ingestSummary(sources, threats);
  const orphan = unlinkedThreats(sources, threats);
  return {
    view: "context_inspector",
    id: sessionId,
    generated_at: new Date().toISOString(),
    data: {
      session_id: sessionId,
      summary,
      ingest_timeline: timeline.map((step) => ({
        step: step.index,
        source_id: step.source.source_id,
        origin: step.source.origin,
        trust_level: step.source.trust_level,
        scan_action: step.source.scan_action,
        findings: step.source.findings,
        created_at: step.source.created_at,
        linked_threat_ids: step.linkedThreats.map((t) => t.threat_id),
      })),
      sources: sortSourcesIngestOrder(sources),
      threats,
      unlinked_threat_ids: orphan.map((t) => t.threat_id),
    },
    links: {
      sources: `/api/agent-view/sources/${sessionId}`,
      threats: `/api/agent-view/threats/${sessionId}`,
      incident: `/api/agent-view/incident/${sessionId}`,
      human_view: `#context_inspector?session=${sessionId}`,
      ...links,
    },
    hints: {
      ingest_order: "sources sorted created_at ASC — ingest checkpoint scan_action on each row",
      provenance:
        "threats linked when evidence_excerpt names the source origin (retrieved_source_in_side_effect)",
    },
  };
}
