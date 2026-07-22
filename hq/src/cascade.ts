/** Shared Agent → version → model → session cascade reducer (Wave A / WS1). */

export type CascadeLane = "versioned" | "unversioned";

export type CascadeState = {
  agentId: string;
  versionId: string;
  model: string;
  sessionId: string;
  /** Honest label when no agent_versions rows exist for the agent. */
  lane: CascadeLane;
};

export type CascadeAction =
  | { type: "hydrate"; partial: Partial<CascadeState> }
  | { type: "set_agent"; agentId: string }
  | { type: "set_version"; versionId: string; model?: string }
  | { type: "set_unversioned"; model?: string }
  | { type: "set_model"; model: string }
  | { type: "set_session"; sessionId: string };

export const emptyCascade = (): CascadeState => ({
  agentId: "",
  versionId: "",
  model: "",
  sessionId: "",
  lane: "versioned",
});

/**
 * Parent changes clear children:
 * agent → clears version/model/session
 * version → clears session (model may be set from version.model)
 * model → clears session
 */
export function cascadeReducer(state: CascadeState, action: CascadeAction): CascadeState {
  switch (action.type) {
    case "hydrate":
      return { ...state, ...action.partial };
    case "set_agent":
      return {
        agentId: action.agentId,
        versionId: "",
        model: "",
        sessionId: "",
        lane: "versioned",
      };
    case "set_version":
      return {
        ...state,
        versionId: action.versionId,
        // Explicit model (including "") wins; omit only when key absent — callers
        // should pass version.model so deep links without model don't keep stale ids.
        model: action.model !== undefined ? action.model : state.model,
        sessionId: "",
        lane: "versioned",
      };
    case "set_unversioned":
      return {
        ...state,
        versionId: "",
        // Preserve current model when switching lanes unless a new model is provided.
        model: action.model !== undefined ? action.model : state.model,
        sessionId: "",
        lane: "unversioned",
      };
    case "set_model":
      return { ...state, model: action.model, sessionId: "" };
    case "set_session":
      return { ...state, sessionId: action.sessionId };
    default:
      return state;
  }
}

/** Prefer hero session ids when present in the filtered set. */
export function preferHeroSession(
  sessionIds: string[],
  heroes: string[],
  prefer?: string,
): string {
  if (prefer && sessionIds.includes(prefer)) return prefer;
  for (const id of heroes) {
    if (sessionIds.includes(id)) return id;
  }
  return sessionIds[0] ?? "";
}

/** Pick initial version: prefer deep-link, else newest (first in newest-first list). */
export function preferVersion(
  versionIds: string[],
  prefer?: string,
): string {
  if (prefer && versionIds.includes(prefer)) return prefer;
  return versionIds[0] ?? "";
}
