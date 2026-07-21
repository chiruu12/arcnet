import { useEffect, useState } from "react";
import { api } from "./api";
import type { Mode, View } from "./types";
import { CaseFiles } from "./views/CaseFiles";
import { Dashboards } from "./views/Dashboards";
import { FleetHealth } from "./views/FleetHealth";
import { Signals } from "./views/Signals";
import { SourcesTrust } from "./views/SourcesTrust";
import { TimeMachine } from "./views/TimeMachine";

const NAV: { group: string; items: View[] }[] = [
  { group: "// observe", items: ["fleet_health", "signals", "sources_trust"] },
  { group: "// improve", items: ["time_machine", "case_files", "dashboards"] },
];

export function App() {
  const [view, setView] = useState<View>("fleet_health");
  const [mode, setMode] = useState<Mode>("human");
  const [apiUp, setApiUp] = useState<boolean | null>(null);
  const [miniFleet, setMiniFleet] = useState<{ id: string; hot: boolean }[]>([]);

  useEffect(() => {
    let cancelled = false;
    api
      .fleet()
      .then((f) => {
        if (cancelled) return;
        setApiUp(true);
        setMiniFleet(
          f.map((a) => ({
            id: a.agent_id,
            hot: (a.health?.threats_24h ?? 0) > 0 || (a.health?.anomalies_24h ?? 0) > 0,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setApiUp(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="wordmark">{"> arcnet"}</div>
        {NAV.map((g) => (
          <div className="nav-group" key={g.group}>
            <div className="nav-eyebrow">{g.group}</div>
            {g.items.map((item) => (
              <button
                key={item}
                className={`nav-item ${view === item ? "active" : ""}`}
                onClick={() => setView(item)}
              >
                {item}
              </button>
            ))}
          </div>
        ))}
        <div className="sidebar-footer">
          <div className="nav-eyebrow">{"// fleet"}</div>
          {miniFleet.length === 0 && <div className="mini-row dim">no agents</div>}
          {miniFleet.map((a) => (
            <div className="mini-row" key={a.id}>
              <span className={`dot ${a.hot ? "danger" : "ok"}`} />
              {a.id}
            </div>
          ))}
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="breadcrumb">
            {view}
            {apiUp === null ? " · connecting" : apiUp ? " · live" : " · api_down"}
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
        </header>

        <main className="content">
          {apiUp === false && (
            <p className="err">
              seam: arcnet-server unreachable — start it with `make server` (or
              scripts/run-demo.sh) and reload.
            </p>
          )}
          {view === "fleet_health" && <FleetHealth mode={mode} />}
          {view === "signals" && <Signals mode={mode} />}
          {view === "sources_trust" && <SourcesTrust mode={mode} />}
          {view === "time_machine" && <TimeMachine mode={mode} />}
          {view === "case_files" && <CaseFiles mode={mode} />}
          {view === "dashboards" && <Dashboards mode={mode} />}
        </main>
      </div>
    </div>
  );
}
