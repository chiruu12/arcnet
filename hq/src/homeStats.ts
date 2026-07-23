import type { FleetRow, ThreatRow } from "./types";

export type HomeStatKey = "agents" | "sessions" | "threats_blocked" | "signals" | "replays";

export type HomeStatsSnapshot = {
  agents: number | null;
  sessions: number | null;
  threats_blocked: number | null;
  threats_blocked_partial: boolean;
  signals: number | null;
  replays: number | null;
};

/** Count registered agents from fleet rows. */
export function countAgents(fleet: FleetRow[] | null): number | null {
  if (fleet === null) return null;
  return fleet.length;
}

/** Count blocked threats in a threats page; partial when the page does not cover all rows. */
export function countThreatsBlocked(
  rows: ThreatRow[],
  total: number,
): { count: number; partial: boolean } {
  const blocked = rows.filter((t) => t.action === "block").length;
  return { count: blocked, partial: rows.length < total };
}

/** Format a stat tile value; partial blocked counts render as `N+`. */
export function formatStatValue(value: number | null, partial = false): string {
  if (value === null) return "—";
  if (partial) return `${value}+`;
  return String(value);
}

/** Merge API payloads into a single home stats snapshot. */
export function buildHomeStats(input: {
  fleet: FleetRow[] | null;
  sessionsTotal: number | null;
  threats: ThreatRow[] | null;
  threatsTotal: number;
  signalsTotal: number | null;
  replays: unknown[] | null;
}): HomeStatsSnapshot {
  const threatsBlocked =
    input.threats === null
      ? { count: null as number | null, partial: false }
      : (() => {
          const { count, partial } = countThreatsBlocked(input.threats, input.threatsTotal);
          return { count, partial };
        })();

  return {
    agents: countAgents(input.fleet),
    sessions: input.sessionsTotal,
    threats_blocked: threatsBlocked.count,
    threats_blocked_partial: threatsBlocked.partial,
    signals: input.signalsTotal,
    replays: input.replays === null ? null : input.replays.length,
  };
}
