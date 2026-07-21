import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, Seam, ts } from "../components";
import type { Mode, SourceRow } from "../types";

const ACTION_CLASS: Record<string, string> = {
  block: "danger",
  redact: "warn",
  review: "warn",
  allow: "ok",
};

export function SourcesTrust({ mode }: { mode: Mode }) {
  const [sources, setSources] = useState<SourceRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .sources()
      .then((s) => {
        if (!cancelled) setSources(s);
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
        <h1>GET /api/sources</h1>
        {err && <Seam error={err} />}
        <pre className="agent-json">{JSON.stringify(sources ?? [], null, 2)}</pre>
      </>
    );
  }

  return (
    <>
      <p className="eyebrow">{"// observe"}</p>
      <h1>sources_trust</h1>
      <p className="lede">
        per-agent ingested-source ledger · what unplug scanned, filtered, blocked.
      </p>
      {err && <Seam error={err} />}
      {sources && sources.length === 0 && (
        <Empty hint="no ingested sources recorded — run a scenario that fetches untrusted content (S1)" />
      )}
      {sources && sources.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>time</th>
              <th>agent</th>
              <th>session</th>
              <th>origin</th>
              <th>trust_level</th>
              <th>scan_action</th>
              <th>findings</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.source_id}>
                <td className="dim">{ts(s.created_at)}</td>
                <td>{s.agent_id ?? "—"}</td>
                <td className="dim">{s.session_id ?? "—"}</td>
                <td className="wrap">{s.origin ?? "—"}</td>
                <td>{s.trust_level ?? "—"}</td>
                <td>
                  <span className={`badge ${ACTION_CLASS[s.scan_action ?? ""] ?? "ok"}`}>
                    [{(s.scan_action ?? "n/a").toUpperCase()}]
                  </span>
                </td>
                <td>{s.findings}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
