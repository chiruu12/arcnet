import { useEffect, useState } from "react";
import { api, subscribeBus } from "../api";
import { Empty, Seam, ts } from "../components";
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
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>GET /api/signals</h1>
        {err && <Seam error={err} />}
        <pre className="agent-json">{JSON.stringify(signals ?? [], null, 2)}</pre>
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
      {signals && signals.length === 0 && (
        <Empty hint="no signals yet — trigger a scenario (scripts/run_scenario.py) or run-demo.sh" />
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
