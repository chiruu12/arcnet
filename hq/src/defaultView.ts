import type { View } from "./types";

const KNOWN_VIEWS = new Set<View>([
  "home",
  "fleet_health",
  "signals",
  "hitl",
  "sources_trust",
  "time_machine",
  "case_files",
  "dashboards",
  "hq_agent",
]);

/** Resolve hash path segment to a view; empty → home, unknown → home. */
export function resolveViewFromPath(path: string): View {
  const trimmed = path.trim();
  if (trimmed === "") return "home";
  return KNOWN_VIEWS.has(trimmed as View) ? (trimmed as View) : "home";
}
