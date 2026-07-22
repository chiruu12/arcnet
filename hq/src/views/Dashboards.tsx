import { useEffect, useState } from "react";
import { api, type SignozStatus } from "../api";
import type { Mode } from "../types";

/** Fallback only before /api/signoz/status returns (or if the probe fails). */
const SIGNOZ_FALLBACK: string = import.meta.env.VITE_SIGNOZ_URL ?? "http://localhost:8080";

const LINKS: { name: string; path: string; desc: string }[] = [
  {
    name: "fleet_overview",
    path: "/dashboard",
    desc: "sessions, cost, token burn per agent (SigNoz dashboard)",
  },
  {
    name: "threat_center",
    path: "/dashboard",
    desc: "guard actions by checkpoint/category, blocked tool calls (ClickHouse-SQL panel)",
  },
  {
    name: "reliability",
    path: "/dashboard",
    desc: "loop kills, seasonal-anomaly rule next to griffin fallback",
  },
  { name: "traces", path: "/traces-explorer", desc: "raw span explorer for any session trace_id" },
  { name: "alerts", path: "/alerts", desc: "v5 query-based alert rules → /webhooks/signoz" },
];

function baseUrl(s: SignozStatus | null): string {
  const raw = s?.signoz_url || SIGNOZ_FALLBACK;
  return raw.replace(/\/$/, "");
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
  return {
    text: `signoz UI reachable at ${s.signoz_url} · ${key} · ${query}. pick a provisioned dashboard in the SigNoz UI (Fleet / Threats / Cost) — list links open the same instance.`,
    warn: !s.api_key_present || s.query_range_ok === false,
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

  const body = (
    <>
      <p className="lede">
        deep-links into SigNoz. arcnet keeps replay + case files SQLite-primary, so everything else
        in this app works without these.
      </p>
      <p className={`meta ${line.warn ? "warn-text" : ""}`}>{line.text}</p>
      <div className="grid">
        {LINKS.map((l) => (
          <a
            key={l.name}
            className="agent link-card"
            href={`${signozBase}${l.path}`}
            target="_blank"
            rel="noreferrer"
          >
            <h3>{l.name}</h3>
            <div className="meta">{`${signozBase}${l.path}`}</div>
            <p className="step">{l.desc}</p>
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
        <pre className="agent-json">
          {JSON.stringify(
            {
              signoz_status: status,
              links: LINKS.map((l) => ({
                name: l.name,
                url: `${signozBase}${l.path}`,
                desc: l.desc,
              })),
            },
            null,
            2,
          )}
        </pre>
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
