/** Pure SigNoz dashboard deep-link helpers for Dashboards view + tests. */

export type DashKey = "fleet_ops" | "threats_trust" | "cost_tokens" | "agno";

export type SignozDashboardStatus = {
  signoz_url?: string;
  dashboards?: Partial<Record<DashKey, string | null>>;
};

export type DashboardLinkDef = {
  name: string;
  key?: DashKey;
  path: string;
  desc: string;
};

export type ResolvedDashboardLink = DashboardLinkDef & {
  href: string;
  uuid?: string;
  resolved: boolean;
};

export function signozBaseUrl(
  status: SignozDashboardStatus | null,
  fallback: string,
): string {
  const raw = status?.signoz_url || fallback;
  return raw.replace(/\/$/, "");
}

export function dashboardUuid(
  status: SignozDashboardStatus | null,
  key: DashKey,
  envDash: Partial<Record<DashKey, string | undefined>> = {},
): string | undefined {
  const fromStatus = status?.dashboards?.[key];
  const fromEnv = envDash[key]?.trim();
  const id = (fromStatus || fromEnv || undefined) ?? undefined;
  return id || undefined;
}

export function dashboardLinkPath(
  status: SignozDashboardStatus | null,
  link: DashboardLinkDef,
  envDash: Partial<Record<DashKey, string | undefined>> = {},
): string {
  if (!link.key) return link.path;
  const id = dashboardUuid(status, link.key, envDash);
  return id ? `/dashboard/${id}` : link.path;
}

export function resolveDashboardLinks(
  status: SignozDashboardStatus | null,
  fallbackBase: string,
  links: DashboardLinkDef[],
  envDash: Partial<Record<DashKey, string | undefined>> = {},
): ResolvedDashboardLink[] {
  const base = signozBaseUrl(status, fallbackBase);
  return links.map((link) => {
    const uuid = link.key ? dashboardUuid(status, link.key, envDash) : undefined;
    const resolved = !link.key || Boolean(uuid);
    const path = link.key && uuid ? `/dashboard/${uuid}` : link.path;
    return {
      ...link,
      uuid,
      resolved,
      href: resolved ? `${base}${path}` : "",
    };
  });
}

export const UNRESOLVED_DASHBOARD_NOTE =
  "UUID unresolved — set SIGNOZ_DASHBOARD_* or re-provision; not linked";
