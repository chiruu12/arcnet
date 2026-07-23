/** Interval while breadcrumb shows api_down — cheap re-probe until live. */
export const API_RECOVER_INTERVAL_MS = 20_000;

/** Re-probe on window focus only when the last probe failed (api_down). */
export function shouldRecoverProbe(apiUp: boolean | null): boolean {
  return apiUp === false;
}

/** Breadcrumb suffix for shell API probe state. */
export function apiBreadcrumbStatus(apiUp: boolean | null): "connecting" | "live" | "api_down" {
  if (apiUp === null) return "connecting";
  return apiUp ? "live" : "api_down";
}
