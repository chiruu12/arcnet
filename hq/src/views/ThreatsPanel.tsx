import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, Seam, ts } from "../components";
import { showingOfTotal } from "../pageLabel";
import type { ThreatRow } from "../types";

const ACTION_CLASS: Record<string, string> = {
  block: "danger",
  redact: "warn",
  review: "warn",
  allow: "ok",
};

const THREATS_PAGE = 30;

export function ThreatsPanel() {
  const [threats, setThreats] = useState<ThreatRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .threatsPage({ limit: THREATS_PAGE, offset: 0 })
      .then((page) => {
        if (!cancelled) {
          setThreats(page.rows);
          setTotal(page.total);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="threats-panel">
      <p className="eyebrow">{"// threats"}</p>
      <h2>recent guard findings</h2>
      <p className="lede dim">unplug telemetry · GET /api/threats</p>
      {err && <Seam error={err} />}
      {!err && !threats && <p className="lede">loading…</p>}
      {threats && threats.length === 0 && (
        <Empty hint="no threats recorded — run a guarded session (e.g. scenario S1) with the server up" />
      )}
      {threats && threats.length > 0 && (
        <>
          <p className="dim" role="status">
            {showingOfTotal(threats.length, total)}
            {total > threats.length ? ` · page size ${THREATS_PAGE}` : ""}
          </p>
          <table className="data-table compact">
            <thead>
              <tr>
                <th>time</th>
                <th>agent</th>
                <th>checkpoint</th>
                <th>action</th>
                <th>category</th>
                <th>risk</th>
                <th>session</th>
              </tr>
            </thead>
            <tbody>
              {threats.map((t) => (
                <tr key={t.threat_id}>
                  <td className="dim">{ts(t.created_at)}</td>
                  <td>
                    <code>{t.agent_id ?? "—"}</code>
                  </td>
                  <td>{t.checkpoint ?? "—"}</td>
                  <td>
                    <span className={`badge ${ACTION_CLASS[t.action ?? ""] ?? "ok"}`}>
                      [{(t.action ?? "n/a").toUpperCase()}]
                    </span>
                  </td>
                  <td>{t.category ?? "—"}</td>
                  <td>{t.risk_score ?? "—"}</td>
                  <td className="dim">
                    <code>{t.session_id ?? "—"}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
