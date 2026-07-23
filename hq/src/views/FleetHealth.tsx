import { useEffect, useState } from "react";
import { api, type GriffinStatus } from "../api";
import { AgentJson, Empty, Seam } from "../components";
import type { FleetRow, Mode } from "../types";
import { ThreatsPanel } from "./ThreatsPanel";

function MadStrip({
  status,
  err,
  onOpenSignals,
}: {
  status: GriffinStatus | null;
  err: string | null;
  onOpenSignals?: (agentId: string) => void;
}) {
  if (err) {
    return (
      <div className="mad-strip">
        <Seam error={`griffin MAD status unavailable — ${err}`} />
      </div>
    );
  }
  if (!status) {
    return (
      <div className="mad-strip">
        <p className="lede">loading griffin MAD…</p>
      </div>
    );
  }
  const last = status.last_anomaly;
  const source = status.series_source || "none";
  return (
    <div className="mad-strip">
      <p className="eyebrow">{"// griffin · MAD"}</p>
      <div className="control-bar">
        <span>
          estimator=<code>MAD</code>
        </span>
        <span>
          status=<code>{status.status}</code>
        </span>
        <span className="dim">
          series={status.series_count ?? 0} · ready={status.ready_count ?? 0} · warming=
          {status.warming_count ?? 0}
        </span>
        <span className="dim">
          source=<code>{source}</code>
          {source === "seed" ? " (cold demo)" : ""}
          {source === "sqlite_proxy" ? " (SQLite usage — honest proxy)" : ""}
        </span>
      </div>
      {last ? (
        <p className="lede">
          last outlier: <code>{last.series_id ?? "—"}</code>
          {last.z != null ? ` z=${last.z}` : ""}
          {last.agent_id ? (
            <>
              {" · "}
              <button
                type="button"
                className="btn ghost"
                onClick={() => onOpenSignals?.(last.agent_id!)}
              >
                signals:{last.agent_id}
              </button>
            </>
          ) : null}
        </p>
      ) : (
        <Empty hint="no MAD outliers yet — warming or no series (seed / sqlite_proxy / signoz)" />
      )}
      <p className="dim">{status.honesty ?? "Griffin = MAD. TabFM not live."}</p>
    </div>
  );
}

export function FleetHealth({
  mode,
  onOpenAgent,
  onOpenSignals,
}: {
  mode: Mode;
  onOpenAgent?: (agentId: string) => void;
  onOpenSignals?: (agentId: string) => void;
}) {
  const [fleet, setFleet] = useState<FleetRow[] | null>(null);
  const [griffin, setGriffin] = useState<GriffinStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [griffinErr, setGriffinErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .fleet()
      .then((f) => {
        if (!cancelled) setFleet(f);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    api
      .griffinStatus()
      .then((g) => {
        if (!cancelled) {
          setGriffin(g);
          setGriffinErr(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setGriffinErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (mode === "agent") return <AgentJson view="fleet" id="all" />;

  return (
    <>
      <p className="eyebrow">{"// observe"}</p>
      <h1>fleet_health</h1>
      <p className="lede">
        agents · trust posture · threats · cost · griffin MAD. click an agent to open its case_files
        cascade; hot agents also deep-link to signals.
      </p>
      <MadStrip status={griffin} err={griffinErr} onOpenSignals={onOpenSignals} />
      <ThreatsPanel />
      {err && <Seam error={err} />}
      {!err && !fleet && <p className="lede">loading…</p>}
      {fleet && fleet.length === 0 && (
        <Empty hint="no agents registered — start the server and run an instrumented agent (or seed with ./scripts/run-demo.sh)" />
      )}
      {fleet && fleet.length > 0 && (
        <div className="grid">
          {fleet.map((a) => {
            const hot = (a.health?.threats_24h ?? 0) > 0 || (a.health?.anomalies_24h ?? 0) > 0;
            return (
              <article
                key={a.agent_id}
                className={`agent clickable ${a.exposure === "forward_facing" ? "forward" : ""}`}
                role="button"
                tabIndex={0}
                onClick={() => onOpenAgent?.(a.agent_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onOpenAgent?.(a.agent_id);
                  }
                }}
              >
                <h3>
                  <span className={`dot ${hot ? "danger" : "ok"}`} />
                  {a.name || a.agent_id}
                  {a.exposure === "forward_facing" && (
                    <span className="badge danger sp-l">[FORWARD]</span>
                  )}
                </h3>
                <div className="meta">
                  {a.agent_id} · {a.role || "—"} · {a.model || "—"}
                </div>
                {(
                  [
                    ["sessions_24h", a.health.sessions_24h],
                    ["threats_24h", a.health.threats_24h],
                    ["blocked_24h", a.health.blocked_24h],
                    ["cost_24h_usd", a.health.cost_24h_usd],
                    ["anomalies_24h", a.health.anomalies_24h],
                    ["active_signals", a.health.active_signals],
                  ] as const
                ).map(([k, v]) => (
                  <div className="stat-row" key={k}>
                    <span>{k}</span>
                    <span className={k === "threats_24h" && Number(v) > 0 ? "val-danger" : ""}>
                      {v}
                    </span>
                  </div>
                ))}
                {hot && onOpenSignals && (
                  <button
                    type="button"
                    className="btn ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenSignals(a.agent_id);
                    }}
                  >
                    open_signals()
                  </button>
                )}
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}
