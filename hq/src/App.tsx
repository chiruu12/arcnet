import { useEffect, useState } from "react";

type View = "fleet_health" | "time_machine" | "signals" | "case_files";

type FleetRow = {
  agent_id: string;
  name: string | null;
  role: string | null;
  exposure: string | null;
  model: string | null;
  health: {
    sessions_24h: number;
    threats_24h: number;
    blocked_24h: number;
    cost_24h_usd: number;
    anomalies_24h: number;
    active_signals: number;
  };
};

type Verdict = {
  replay_id: string;
  session_id: string;
  scenario: string;
  baseline: Record<string, unknown>;
  candidate: Record<string, unknown>;
  divergences: { step: number; note: string }[];
  verdict: string;
  confidence: string;
  recommendation: string;
};

const API = import.meta.env.VITE_ARCNET_API ?? "";

const MOCK_FLEET: FleetRow[] = [
  {
    agent_id: "agent_j",
    name: "Agent J",
    role: "support/ops",
    exposure: "forward_facing",
    model: "gpt-4o-mini",
    health: {
      sessions_24h: 12,
      threats_24h: 4,
      blocked_24h: 3,
      cost_24h_usd: 0.084,
      anomalies_24h: 1,
      active_signals: 1,
    },
  },
  {
    agent_id: "agent_l",
    name: "Agent L",
    role: "fleet background",
    exposure: "internal",
    model: "gpt-4o-mini",
    health: {
      sessions_24h: 40,
      threats_24h: 0,
      blocked_24h: 0,
      cost_24h_usd: 0.021,
      anomalies_24h: 0,
      active_signals: 0,
    },
  },
  {
    agent_id: "agent_o",
    name: "Agent O",
    role: "fleet background",
    exposure: "internal",
    model: "gpt-4o-mini",
    health: {
      sessions_24h: 38,
      threats_24h: 0,
      blocked_24h: 0,
      cost_24h_usd: 0.019,
      anomalies_24h: 0,
      active_signals: 0,
    },
  },
];

export function App() {
  const [view, setView] = useState<View>("fleet_health");
  const [mode, setMode] = useState<"human" | "agent">("human");
  const [fleet, setFleet] = useState<FleetRow[]>(MOCK_FLEET);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const base = API || "";
        const [f, v] = await Promise.all([
          fetch(`${base}/api/fleet`).then((r) => (r.ok ? r.json() : null)),
          fetch(`${base}/api/mock/time-machine`).then((r) => (r.ok ? r.json() : null)),
        ]);
        if (cancelled) return;
        if (Array.isArray(f) && f.length > 0) {
          setFleet(f);
          setLive(true);
        }
        if (v) setVerdict(v);
        setErr(null);
      } catch (e) {
        if (!cancelled) {
          setErr(String(e));
          // keep mocks
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="wordmark">{"> arcnet"}</div>
        <div className="nav-group">
          <div className="nav-eyebrow">{"// observe"}</div>
          <button
            className={`nav-item ${view === "fleet_health" ? "active" : ""}`}
            onClick={() => setView("fleet_health")}
          >
            fleet_health
          </button>
          <button
            className={`nav-item ${view === "signals" ? "active" : ""}`}
            onClick={() => setView("signals")}
          >
            signals
          </button>
        </div>
        <div className="nav-group">
          <div className="nav-eyebrow">{"// improve"}</div>
          <button
            className={`nav-item ${view === "time_machine" ? "active" : ""}`}
            onClick={() => setView("time_machine")}
          >
            time_machine
          </button>
          <button
            className={`nav-item ${view === "case_files" ? "active" : ""}`}
            onClick={() => setView("case_files")}
          >
            case_files
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="breadcrumb">
            {view}
            {live ? " · live" : " · mock"}
          </div>
          <span className="tag">demo</span>
          <div className="toggle" role="group" aria-label="view mode">
            <button className={mode === "human" ? "on" : ""} onClick={() => setMode("human")}>
              human_view
            </button>
            <button className={mode === "agent" ? "on" : ""} onClick={() => setMode("agent")}>
              agent_view
            </button>
          </div>
          <button className="btn" type="button">
            replay.run()
          </button>
        </header>

        <main className="content">
          {err && <p className="err">seam: {err} — rendering mock_data()</p>}
          {view === "fleet_health" && (
            <FleetHealth fleet={fleet} mode={mode} />
          )}
          {view === "time_machine" && (
            <TimeMachine verdict={verdict} mode={mode} />
          )}
          {view === "signals" && (
            <Placeholder
              title="signals.feed()"
              body="live SSE feed wires in Phase 5 — bus is live on /signals/stream"
            />
          )}
          {view === "case_files" && (
            <Placeholder
              title="case_files.export()"
              body="Case File exporter lands in Phase 5"
            />
          )}
        </main>
      </div>
    </div>
  );
}

function FleetHealth({ fleet, mode }: { fleet: FleetRow[]; mode: "human" | "agent" }) {
  if (mode === "agent") {
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>fleet_health</h1>
        <pre className="agent-json">{JSON.stringify({ view: "fleet", data: fleet }, null, 2)}</pre>
      </>
    );
  }
  return (
    <>
      <p className="eyebrow">{"// observe"}</p>
      <h1>fleet_health</h1>
      <p className="lede">
        agents · trust posture · threats · cost · griffin anomalies. forward_facing flagged.
      </p>
      <div className="grid">
        {fleet.map((a) => {
          const hot = (a.health?.threats_24h ?? 0) > 0 || (a.health?.anomalies_24h ?? 0) > 0;
          return (
            <article
              key={a.agent_id}
              className={`agent ${a.exposure === "forward_facing" ? "forward" : ""}`}
            >
              <h3>
                <span className={`dot ${hot ? "danger" : "ok"}`} />
                {a.name || a.agent_id}
              </h3>
              <div className="meta">
                {a.agent_id} · {a.exposure} · {a.model || "—"}
              </div>
              <div className="stat-row">
                <span>sessions_24h</span>
                <span>{a.health.sessions_24h}</span>
              </div>
              <div className="stat-row">
                <span>threats_24h</span>
                <span>{a.health.threats_24h}</span>
              </div>
              <div className="stat-row">
                <span>blocked_24h</span>
                <span>{a.health.blocked_24h}</span>
              </div>
              <div className="stat-row">
                <span>cost_24h_usd</span>
                <span>{a.health.cost_24h_usd}</span>
              </div>
              <div className="stat-row">
                <span>anomalies_24h</span>
                <span>{a.health.anomalies_24h}</span>
              </div>
              <div className="stat-row">
                <span>active_signals</span>
                <span>{a.health.active_signals}</span>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}

function TimeMachine({
  verdict,
  mode,
}: {
  verdict: Verdict | null;
  mode: "human" | "agent";
}) {
  const v =
    verdict ??
    ({
      replay_id: "r_08c1",
      session_id: "s_77b2",
      scenario: "S4",
      baseline: {
        model: "gpt-4o-mini",
        goal_reached: "killed",
        steps: 19,
        cost_usd: 0.062,
      },
      candidate: {
        model: "gpt-4o",
        goal_reached: "partial",
        steps: 5,
        cost_usd: 0.011,
        note: "flagged endless pagination",
      },
      divergences: [{ step: 5, note: "candidate stopped calling paginate_records" }],
      verdict: "improved",
      confidence: "mock",
      recommendation: "route batch/reconcile tasks to gpt-4o",
    } as Verdict);

  if (mode === "agent") {
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>time_machine</h1>
        <pre className="agent-json">{JSON.stringify({ view: "replay", data: v }, null, 2)}</pre>
      </>
    );
  }

  const b = v.baseline as Record<string, unknown>;
  const c = v.candidate as Record<string, unknown>;

  return (
    <>
      <p className="eyebrow">{"// counterfactual_replay"}</p>
      <h1>would a different model have stopped the loop?</h1>
      <p className="lede">
        baseline {String(b.model)} [recorded] ⇄ candidate {String(c.model)} [replay] ·
        tool_outputs=mocked · scenario={v.scenario}
      </p>
      <div className="diff">
        <div className="col exploited">
          <h3>
            {String(b.model)}{" "}
            <span className="badge danger">[KILLED]</span>
          </h3>
          <p className="step">1. goal → reconcile all records</p>
          <p className="step">2. paginate_records → next_cursor forever</p>
          <p className="step">3. tokens climb · griffin flags · kill</p>
          <p className="step">
            4. outcome goal_reached={String(b.goal_reached)} steps={String(b.steps)}
          </p>
        </div>
        <div className="col resisted">
          <h3>
            {String(c.model)}{" "}
            <span className="badge ok">[STOPPED]</span>
          </h3>
          <p className="step">1. same goal · same mocked pages</p>
          <p className="step">2. notices endless pagination</p>
          <p className="step">3. reports instead of looping</p>
          <p className="step">
            4. outcome goal_reached={String(c.goal_reached)} steps={String(c.steps)}
          </p>
        </div>
      </div>
      <div className="verdict">
        <div className="traffic">
          <i className="r" />
          <i className="y" />
          <i className="g" />
        </div>
        <div className="meta">replay.diff · {v.replay_id} · {v.confidence}</div>
        <table>
          <tbody>
            <tr>
              <td>goal_reached</td>
              <td>
                {String(b.goal_reached)} → {String(c.goal_reached)}
              </td>
            </tr>
            <tr>
              <td>steps</td>
              <td>
                {String(b.steps)} → {String(c.steps)}
              </td>
            </tr>
            <tr>
              <td>cost_usd</td>
              <td>
                {String(b.cost_usd)} → {String(c.cost_usd)}
              </td>
            </tr>
            <tr>
              <td>verdict</td>
              <td>{v.verdict}</td>
            </tr>
          </tbody>
        </table>
        <div className="rec">{v.recommendation}</div>
        <div style={{ marginTop: 12 }}>
          <button className="btn" type="button">
            hand_to(claude_code)
          </button>
          <button className="btn ghost" type="button">
            replay_corpus(n=12)
          </button>
        </div>
      </div>
    </>
  );
}

function Placeholder({ title, body }: { title: string; body: string }) {
  return (
    <>
      <p className="eyebrow">{"// scaffold"}</p>
      <h1>{title}</h1>
      <p className="lede">{body}</p>
    </>
  );
}
