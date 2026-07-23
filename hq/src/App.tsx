import { useEffect, useState } from "react";
import { api } from "./api";
import { formatHash, navigate, parseHash, type HashState, writeHash } from "./hash";
import type { Mode, View } from "./types";
import { CaseFiles } from "./views/CaseFiles";
import { Dashboards } from "./views/Dashboards";
import { FleetHealth } from "./views/FleetHealth";
import { HqAgent } from "./views/HqAgent";
import { Hitl } from "./views/Hitl";
import { Signals } from "./views/Signals";
import { SourcesTrust } from "./views/SourcesTrust";
import { TimeMachine } from "./views/TimeMachine";

const NAV: { group: string; items: View[] }[] = [
  { group: "// observe", items: ["fleet_health", "signals", "hitl", "sources_trust"] },
  { group: "// improve", items: ["time_machine", "case_files", "dashboards", "hq_agent"] },
];

export function App() {
  const [hash, setHash] = useState<HashState>(() =>
    typeof window !== "undefined" ? parseHash() : { view: "fleet_health" },
  );
  const [mode, setMode] = useState<Mode>("human");
  const [apiUp, setApiUp] = useState<boolean | null>(null);
  const [miniFleet, setMiniFleet] = useState<{ id: string; hot: boolean }[]>([]);

  useEffect(() => {
    const onHash = () => setHash(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const next = formatHash(hash);
    if (window.location.hash !== next) {
      writeHash(hash);
    }
  }, [hash]);

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

  function setView(view: View) {
    setHash((cur) => ({ view, agent: cur.agent }));
  }

  function patchHash(patch: Partial<HashState>) {
    setHash((cur) => ({ ...cur, ...patch, view: patch.view ?? cur.view }));
  }

  const { view } = hash;

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
            <button
              type="button"
              className={`mini-row clickable ${hash.agent === a.id ? "active" : ""}`}
              key={a.id}
              title={`open case_files for ${a.id}`}
              onClick={() =>
                navigate({
                  view: "case_files",
                  agent: a.id,
                  version: "",
                  session: "",
                  model: "",
                })
              }
            >
              <span className={`dot ${a.hot ? "danger" : "ok"}`} />
              {a.id}
            </button>
          ))}
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="breadcrumb">
            {view}
            {hash.agent ? ` · ${hash.agent}` : ""}
            {hash.version ? ` · ${hash.version}` : ""}
            {apiUp === null ? " · connecting" : apiUp ? " · live" : " · api_down"}
          </div>
          <span className="tag">local</span>
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
              seam: arcnet-server unreachable — start uvicorn on :8000 (or `./scripts/run-demo.sh`
              for a seeded bring-up) and reload. Views below may show empty or stale data until the
              API is back.
            </p>
          )}
          {view === "fleet_health" && (
            <FleetHealth
              mode={mode}
              onOpenAgent={(agentId) =>
                navigate({
                  view: "case_files",
                  agent: agentId,
                  version: "",
                  session: "",
                  model: "",
                })
              }
              onOpenSignals={(agentId) =>
                navigate({ view: "signals", agent: agentId, session: "", model: "" })
              }
            />
          )}
          {view === "signals" && (
            <Signals
              mode={mode}
              agentId={hash.agent}
              onAgentChange={(agent) => patchHash({ agent: agent || undefined })}
            />
          )}
          {view === "hitl" && <Hitl mode={mode} />}
          {view === "sources_trust" && (
            <SourcesTrust
              mode={mode}
              agentId={hash.agent}
              onAgentChange={(agent) => patchHash({ agent: agent || undefined })}
            />
          )}
          {view === "time_machine" && (
            <TimeMachine
              mode={mode}
              deepLink={{
                agent: hash.agent,
                version: hash.version,
                session: hash.session,
                model: hash.model,
              }}
              onDeepLinkChange={(next) =>
                patchHash({
                  agent: next.agent,
                  version: next.version,
                  model: next.model,
                  session: next.session,
                })
              }
            />
          )}
          {view === "case_files" && (
            <CaseFiles
              mode={mode}
              deepLink={{
                agent: hash.agent,
                version: hash.version,
                session: hash.session,
                model: hash.model,
              }}
              onDeepLinkChange={(next) =>
                patchHash({
                  agent: next.agent,
                  version: next.version,
                  model: next.model,
                  session: next.session,
                })
              }
            />
          )}
          {view === "dashboards" && <Dashboards mode={mode} />}
          {view === "hq_agent" && (
            <HqAgent
              deepLink={{
                agent: hash.agent,
                version: hash.version,
                session: hash.session,
                model: hash.model,
              }}
              onDeepLinkChange={(next) =>
                patchHash({
                  agent: next.agent,
                  version: next.version,
                  model: next.model,
                  session: next.session,
                })
              }
            />
          )}
        </main>
      </div>
    </div>
  );
}
