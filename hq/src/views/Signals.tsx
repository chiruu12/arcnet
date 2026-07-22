import { useEffect, useState } from "react";
import { api, subscribeBus } from "../api";
import { AgentJson, Empty, Seam, ts } from "../components";
import type { Mode, SignalRow } from "../types";

const KIND_CLASS: Record<string, string> = {
  kill: "danger",
  pause: "warn",
  steer: "ok",
};

export function Signals({ mode }: { mode: Mode }) {
  const [signals, setSignals] = useState<SignalRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [liveCount, setLiveCount] = useState(0);
  const [agentRef, setAgentRef] = useState("all");

  useEffect(() => {
    let cancelled = false;
    api
      .fleet()
      .then((f) => {
        if (!cancelled && f.length > 0) setAgentRef((cur) => (cur === "all" ? f[0].agent_id : cur));
      })
      .catch(() => {
        /* fleet optional for raw list */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .signals()
      .then((s) => {
        if (!cancelled) setSignals(s);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    const unsubscribe = subscribeBus((ev) => {
      if (cancelled || ev.event !== "signal") return;
      const row = ev.data as unknown as SignalRow;
      if (!row.signal_id) return;
      setSignals((prev) => {
        const rest = (prev ?? []).filter((s) => s.signal_id !== row.signal_id);
        return [row, ...rest];
      });
      setLiveCount((n) => n + 1);
    });
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  if (mode === "agent") {
    if (!agentRef || agentRef === "all") {
      return (
        <>
          <p className="eyebrow">{"// agent_view"}</p>
          <h1>signals</h1>
          <Empty hint="loading agent ref…" />
        </>
      );
    }
    return <AgentJson view="signals" id={agentRef} />;
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
      {signals && signals.length === 0 && (
        <Empty hint="no signals yet — run a guarded agent session, or: PYTHONPATH=sdk:agents uv run python agents/scenarios/runner.py --scenario S1" />
      )}
      {signals && signals.length > 0 && (
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
      )}
    </>
  );
}
