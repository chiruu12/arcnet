import { useEffect, useState } from "react";
import { api, type SignozStatus } from "../api";
import { AgentJson } from "../components";
import type { Mode } from "../types";

/** Fallback only before /api/signoz/status returns (or if the probe fails). */
const SIGNOZ_FALLBACK: string = import.meta.env.VITE_SIGNOZ_URL ?? "http://localhost:8080";

type DashKey = "fleet_ops" | "threats_trust" | "cost_tokens" | "agno";

const ENV_DASH: Record<DashKey, string | undefined> = {
  fleet_ops: import.meta.env.VITE_SIGNOZ_DASHBOARD_FLEET,
  threats_trust: import.meta.env.VITE_SIGNOZ_DASHBOARD_THREATS,
  cost_tokens: import.meta.env.VITE_SIGNOZ_DASHBOARD_COST,
  agno: import.meta.env.VITE_SIGNOZ_DASHBOARD_AGNO,
};

type LinkDef = {
  name: string;
  key?: DashKey;
  path: string;
  desc: string;
};

const LINKS: LinkDef[] = [
  {
    name: "fleet_overview",
    key: "fleet_ops",
    path: "/dashboard",
    desc: "sessions, cost, token burn per agent (SigNoz dashboard)",
  },
  {
    name: "threat_center",
    key: "threats_trust",
    path: "/dashboard",
    desc: "guard actions by checkpoint/category, blocked tool calls (ClickHouse-SQL panel)",
  },
  {
    name: "cost_tokens",
    key: "cost_tokens",
    path: "/dashboard",
    desc: "token burn and $ cost by agent / model",
  },
  {
    name: "agno",
    key: "agno",
    path: "/dashboard",
    desc: "Agno runtime dashboard (if provisioned)",
  },
  { name: "traces", path: "/traces-explorer", desc: "raw span explorer for any session trace_id" },
  { name: "alerts", path: "/alerts", desc: "v5 query-based alert rules → /webhooks/signoz" },
];

function baseUrl(s: SignozStatus | null): string {
  const raw = s?.signoz_url || SIGNOZ_FALLBACK;
  return raw.replace(/\/$/, "");
}

function dashboardId(s: SignozStatus | null, key: DashKey): string | undefined {
  const fromStatus = s?.dashboards?.[key];
  const fromEnv = ENV_DASH[key]?.trim();
  return (fromStatus || fromEnv || undefined) || undefined;
}

function linkPath(s: SignozStatus | null, link: LinkDef): string {
  if (!link.key) return link.path;
  const id = dashboardId(s, link.key);
  return id ? `/dashboard/${id}` : link.path;
}

function statusLine(
  s: SignozStatus | null,
  err: string | null,
  base: string,
): { text: string; warn: boolean } {
  if (err) {
    return {
      text: `signoz status probe failed (${err}) — deep-links still open ${base}. optional stack; HQ works SQLite-primary without it.`,
      warn: true,
    };
  }
  if (!s) return { text: "probing signoz…", warn: false };
  if (!s.ui_reachable) {
    return {
      text: `signoz UI unreachable at ${s.signoz_url} (optional). start deploy/ casting when you want dashboards/traces; replay + case files stay SQLite-primary.`,
      warn: true,
    };
  }
  const key = s.api_key_present ? "api_key=present" : "api_key=missing";
  const query =
    s.query_range_ok === true
      ? "query_range=ok"
      : s.query_range_ok === false
        ? `query_range=fail (${s.query_note})`
        : s.query_note;
  const resolved = Object.entries(s.dashboards ?? {})
    .filter(([, id]) => id)
    .map(([name]) => name);
  const dashNote =
    resolved.length > 0
      ? ` · dashboards=${resolved.join(",")}`
      : " · dashboards=unresolved (set SIGNOZ_DASHBOARD_* or re-provision)";
  return {
    text: `signoz UI reachable at ${s.signoz_url} · ${key} · ${query}${dashNote}`,
    warn: !s.api_key_present || s.query_range_ok === false || resolved.length === 0,
  };
}

export function Dashboards({ mode }: { mode: Mode }) {
  const [status, setStatus] = useState<SignozStatus | null>(null);
  const [probeErr, setProbeErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .signozStatus()
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch((e: unknown) => {
        if (!cancelled) setProbeErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const signozBase = baseUrl(status);
  const line = statusLine(status, probeErr, signozBase);
  const resolvedLinks = LINKS.map((l) => ({
    ...l,
    href: `${signozBase}${linkPath(status, l)}`,
    uuid: l.key ? dashboardId(status, l.key) : undefined,
  }));

  const body = (
    <>
      <p className="lede">
        deep-links into SigNoz. arcnet keeps replay + case files SQLite-primary, so everything else
        in this app works without these.
      </p>
      <p className={`meta ${line.warn ? "warn-text" : ""}`}>{line.text}</p>
      <div className="grid">
        {resolvedLinks.map((l) => (
          <a
            key={l.name}
            className="agent link-card"
            href={l.href}
            target="_blank"
            rel="noreferrer"
          >
            <h3>{l.name}</h3>
            <div className="meta">{l.href}</div>
            <p className="step">
              {l.desc}
              {l.key && !l.uuid ? " · UUID unresolved — opens dashboard list" : ""}
            </p>
          </a>
        ))}
      </div>
    </>
  );

  if (mode === "agent") {
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>dashboards</h1>
        <AgentJson view="dashboards" id="all" />
      </>
    );
  }

  return (
    <>
      <p className="eyebrow">{"// improve"}</p>
      <h1>dashboards</h1>
      {body}
    </>
  );
}
