import { useEffect, useState } from "react";
import { api, subscribeBus } from "../api";
import { AgentJson, Empty, Seam, ts } from "../components";
import { showingOfTotal } from "../pageLabel";
import type { FleetRow, Mode, SignalRow } from "../types";

const KIND_CLASS: Record<string, string> = {
  kill: "danger",
  pause: "warn",
  steer: "ok",
};

const SIGNALS_PAGE = 40;

export function Signals({
  mode,
  agentId,
  onAgentChange,
}: {
  mode: Mode;
  agentId?: string;
  onAgentChange?: (agentId: string) => void;
}) {
  const [signals, setSignals] = useState<SignalRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [liveCount, setLiveCount] = useState(0);
  const [fleet, setFleet] = useState<FleetRow[]>([]);
  const [agentRef, setAgentRef] = useState(agentId ?? "");

  useEffect(() => {
    if (agentId && agentId !== agentRef) setAgentRef(agentId);
  }, [agentId, agentRef]);

  useEffect(() => {
    let cancelled = false;
    api
      .fleet()
      .then((f) => {
        if (cancelled) return;
        setFleet(f);
        setAgentRef((cur) => {
          if (cur && f.some((a) => a.agent_id === cur)) return cur;
          if (agentId && f.some((a) => a.agent_id === agentId)) return agentId;
          // human list defaults to all; agent_view needs a concrete ref
          return mode === "agent" ? (f[0]?.agent_id ?? "") : cur;
        });
      })
      .catch(() => {
        /* fleet optional for raw list */
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seed once; mode/agentId read at mount
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = {
      ...(agentRef ? { agent_id: agentRef } : {}),
      limit: SIGNALS_PAGE,
      offset: 0,
    };
    api
      .signalsPage(params)
      .then((page) => {
        if (!cancelled) {
          setSignals(page.rows);
          setTotal(page.total);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    const unsubscribe = subscribeBus((ev) => {
      if (cancelled || ev.event !== "signal") return;
      const row = ev.data as unknown as SignalRow;
      if (!row.signal_id) return;
      if (agentRef && row.agent_id !== agentRef) return;
      setSignals((prev) => {
        const rest = (prev ?? []).filter((s) => s.signal_id !== row.signal_id);
        return [row, ...rest].slice(0, SIGNALS_PAGE);
      });
      setTotal((n) => n + 1);
      setLiveCount((n) => n + 1);
    });
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [agentRef]);

  function pickAgent(next: string) {
    setAgentRef(next);
    onAgentChange?.(next);
  }

  if (mode === "agent") {
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>signals</h1>
        {fleet.length > 0 && (
          <div className="control-bar">
            <label>
              agent
              <select value={agentRef} onChange={(e) => pickAgent(e.target.value)}>
                {fleet.map((a) => (
                  <option key={a.agent_id} value={a.agent_id}>
                    {a.agent_id}
                    {a.model ? ` · fleet:${a.model}` : ""}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        {!agentRef && <Empty hint="loading agent ref…" />}
        {agentRef && <AgentJson view="signals" id={agentRef} />}
      </>
    );
  }

  return (
    <>
      <p className="eyebrow">{"// observe"}</p>
      <h1>signals</h1>
      <p className="lede">
        active-defense feed · steer / pause / kill · sse=/signals/stream
        {liveCount > 0 && ` · ${liveCount} live event${liveCount === 1 ? "" : "s"} this session`}
      </p>
      {err && <Seam error={err} />}
      {fleet.length > 0 && (
        <div className="control-bar">
          <label>
            agent
            <select value={agentRef} onChange={(e) => pickAgent(e.target.value)}>
              <option value="">all agents</option>
              {fleet.map((a) => (
                <option key={a.agent_id} value={a.agent_id}>
                  {a.agent_id}
                  {a.model ? ` · fleet:${a.model}` : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
      {signals && signals.length === 0 && (
        <Empty hint="no signals yet — run a guarded agent session, or: PYTHONPATH=sdk:agents uv run python agents/scenarios/runner.py --scenario S1" />
      )}
      {signals && signals.length > 0 && (
        <>
          <p className="dim" role="status">
            {showingOfTotal(signals.length, total)}
            {total > signals.length ? ` · page size ${SIGNALS_PAGE}` : ""}
          </p>
          <table className="data-table">
            <thead>
              <tr>
                <th>time</th>
                <th>kind</th>
                <th>severity</th>
                <th>agent</th>
                <th>session</th>
                <th>reason</th>
                <th>guidance</th>
                <th>source</th>
                <th>status</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s) => (
                <tr key={s.signal_id}>
                  <td className="dim">{ts(s.created_at)}</td>
                  <td>
                    <span className={`badge ${KIND_CLASS[s.kind] ?? "ok"}`}>
                      [{s.kind.toUpperCase()}]
                    </span>
                  </td>
                  <td>{s.severity}</td>
                  <td>{s.agent_id}</td>
                  <td className="dim">{s.session_id ?? "—"}</td>
                  <td className="wrap">{s.reason}</td>
                  <td className="wrap dim">{s.guidance ?? "—"}</td>
                  <td className="dim">{s.source}</td>
                  <td>{s.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
