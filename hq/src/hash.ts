import type { View } from "./types";

const VIEWS = new Set<View>([
  "fleet_health",
  "signals",
  "sources_trust",
  "time_machine",
  "case_files",
  "dashboards",
  "hq_agent",
]);

export type HashState = {
  view: View;
  agent?: string;
  version?: string;
  session?: string;
  model?: string;
};

export function parseHash(raw?: string): HashState {
  const source =
    raw !== undefined
      ? raw
      : typeof window !== "undefined"
        ? window.location.hash
        : "";
  const trimmed = source.replace(/^#/, "");
  const [path, query = ""] = trimmed.split("?");
  const view = VIEWS.has(path as View) ? (path as View) : "fleet_health";
  const params = new URLSearchParams(query);
  const agent = params.get("agent")?.trim() || undefined;
  const version = params.get("version")?.trim() || undefined;
  const session = params.get("session")?.trim() || undefined;
  const model = params.get("model")?.trim() || undefined;
  return { view, agent, version, session, model };
}

/** Build `#view?agent=&version=&session=&model=` — omits empty query keys. */
export function formatHash(state: HashState): string {
  const q = new URLSearchParams();
  if (state.agent) q.set("agent", state.agent);
  if (state.version) q.set("version", state.version);
  if (state.session) q.set("session", state.session);
  if (state.model) q.set("model", state.model);
  const qs = q.toString();
  return qs ? `#${state.view}?${qs}` : `#${state.view}`;
}

export function writeHash(state: HashState): void {
  const next = formatHash(state);
  if (window.location.hash !== next) {
    window.location.hash = next;
  }
}

/** Navigate to a view, optionally carrying agent/version/session/model filters. */
export function navigate(partial: Partial<HashState> & { view: View }): void {
  const cur = parseHash();
  writeHash({
    view: partial.view,
    agent: partial.agent !== undefined ? partial.agent || undefined : cur.agent,
    // Preserve cascade context when callers omit fields (e.g. open Signals).
    version: partial.version !== undefined ? partial.version || undefined : cur.version,
    session: partial.session !== undefined ? partial.session || undefined : cur.session,
    model: partial.model !== undefined ? partial.model || undefined : cur.model,
  });
}
