import type { Mode } from "../types";

const SIGNOZ: string = import.meta.env.VITE_SIGNOZ_URL ?? "http://localhost:8080";

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

export function Dashboards({ mode }: { mode: Mode }) {
  const body = (
    <>
      <p className="lede">
        deep-links into SigNoz. arcnet keeps replay + case files SQLite-primary, so everything else
        in this app works without these.
      </p>
      <p className="meta warn-text">
        signoz containers are DEFERRED (user resource pause) — links resolve when the stack is
        back up. no health probe is made from this page.
      </p>
      <div className="grid">
        {LINKS.map((l) => (
          <a key={l.name} className="agent link-card" href={`${SIGNOZ}${l.path}`} target="_blank" rel="noreferrer">
            <h3>{l.name}</h3>
            <div className="meta">{`${SIGNOZ}${l.path}`}</div>
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
            LINKS.map((l) => ({ name: l.name, url: `${SIGNOZ}${l.path}`, desc: l.desc })),
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
