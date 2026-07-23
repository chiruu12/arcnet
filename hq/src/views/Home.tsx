import { useEffect, useState } from "react";
import { api } from "../api";
import { buildHomeStats, formatStatValue, type HomeStatKey } from "../homeStats";
import { navigate } from "../hash";
import type { Mode, View } from "../types";

const LOOP: { label: string; view: View }[] = [
  { label: "observe", view: "fleet_health" },
  { label: "defend", view: "signals" },
  { label: "replay", view: "time_machine" },
  { label: "case_file", view: "case_files" },
  { label: "improve", view: "hq_agent" },
];

const PILLARS: { title: string; desc: string; view: View }[] = [
  {
    title: "fleet_health",
    desc: "agents · trust posture · threats · cost · griffin MAD",
    view: "fleet_health",
  },
  {
    title: "signals + hitl",
    desc: "live steer/kill feed · human approve/reject queue",
    view: "signals",
  },
  {
    title: "sources_trust",
    desc: "per-agent ingested-source ledger · unplug verdicts",
    view: "sources_trust",
  },
  {
    title: "time_machine",
    desc: "counterfactual replay · baseline vs candidate · verdict",
    view: "time_machine",
  },
  {
    title: "case_files",
    desc: "incident cascade · root cause · export_case_file()",
    view: "case_files",
  },
  {
    title: "dashboards + hq_agent",
    desc: "signoz deep-links · propose→apply model upgrades",
    view: "dashboards",
  },
];

const STAT_KEYS: { key: HomeStatKey; label: string }[] = [
  { key: "agents", label: "agents" },
  { key: "sessions", label: "sessions" },
  { key: "threats_blocked", label: "threats_blocked" },
  { key: "signals", label: "signals" },
  { key: "replays", label: "replays" },
];

function openView(view: View) {
  navigate({ view, agent: "", version: "", session: "", model: "" });
}

export function Home({ mode }: { mode: Mode }) {
  const [stats, setStats] = useState(() => buildHomeStats({
    fleet: null,
    sessionsTotal: null,
    threats: null,
    threatsTotal: 0,
    signalsTotal: null,
    replays: null,
  }));
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setErr(null);

    Promise.all([
      api.fleet().catch(() => null),
      api.sessionsPage({ limit: 1 }).catch(() => null),
      api.threatsPage({ limit: 500, offset: 0 }).catch(() => null),
      api.signalsPage({ limit: 1 }).catch(() => null),
      api.replays().catch(() => null),
    ])
      .then(([fleet, sessionsPage, threatsPage, signalsPage, replays]) => {
        if (cancelled) return;
        if (!fleet && !sessionsPage && !threatsPage && !signalsPage && !replays) {
          setErr("arcnet-server unreachable — stats unavailable until API is back");
        }
        setStats(
          buildHomeStats({
            fleet,
            sessionsTotal: sessionsPage?.total ?? null,
            threats: threatsPage?.rows ?? null,
            threatsTotal: threatsPage?.total ?? 0,
            signalsTotal: signalsPage?.total ?? null,
            replays,
          }),
        );
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (mode === "agent") {
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>home</h1>
        <pre className="agent-json">{JSON.stringify({ view: "home", stats }, null, 2)}</pre>
      </>
    );
  }

  return (
    <>
      <section className="home-hero">
        <p className="wordmark home-wordmark">{"> arcnet"}</p>
        <h1 className="home-tagline">
          make your agents work properly — and enhance them
        </h1>
        <p className="lede home-subtitle">
          observability + active defense for AI-native systems, built on SigNoz.
        </p>
      </section>

      <section className="home-loop" aria-label="arcnet loop">
        <p className="eyebrow">{"// the_loop"}</p>
        <div className="loop-strip">
          {LOOP.map((stage, i) => (
            <span key={stage.label} className="loop-item">
              {i > 0 && <span className="loop-arrow" aria-hidden="true">→</span>}
              <button
                type="button"
                className="loop-stage"
                onClick={() => openView(stage.view)}
              >
                {stage.label}
              </button>
            </span>
          ))}
        </div>
      </section>

      <section className="home-stats" aria-label="live stats">
        <p className="eyebrow">{"// live_stats"}</p>
        {err && <p className="err dim">{err}</p>}
        <div className="stat-tiles">
          {STAT_KEYS.map(({ key, label }) => (
            <div className="stat-tile" key={key}>
              <div className="stat-tile-value">
                {formatStatValue(
                  stats[key],
                  key === "threats_blocked" && stats.threats_blocked_partial,
                )}
              </div>
              <div className="stat-tile-label">{label}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="home-pillars" aria-label="product pillars">
        <p className="eyebrow">{"// views"}</p>
        <div className="pillar-grid">
          {PILLARS.map((p) => (
            <article className="pillar-card" key={p.title}>
              <h3>{p.title}</h3>
              <p className="pillar-desc">{p.desc}</p>
              <button
                type="button"
                className="pillar-link"
                onClick={() => openView(p.view)}
              >
                open →
              </button>
            </article>
          ))}
        </div>
      </section>

      <p className="honesty-strip">
        griffin=mad (tabfm phase 7) · signoz mcp partial · localhost trust · readiness ~64%
      </p>
    </>
  );
}
