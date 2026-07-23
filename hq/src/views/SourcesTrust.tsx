import { useEffect, useState } from "react";
import { api } from "../api";
import { AgentJson, Empty, Seam, ts } from "../components";
import type { FleetRow, Mode, SourceRow } from "../types";

const ACTION_CLASS: Record<string, string> = {
  block: "danger",
  redact: "warn",
  review: "warn",
  allow: "ok",
};

export function SourcesTrust({
  mode,
  agentId,
  onAgentChange,
}: {
  mode: Mode;
  agentId?: string;
  onAgentChange?: (agentId: string) => void;
}) {
  const [sources, setSources] = useState<SourceRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
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
          return f[0]?.agent_id ?? "";
        });
      })
      .catch(() => {
        /* optional */
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    setSources(null);
    setErr(null);
    api
      .sources(agentRef ? { agent_id: agentRef } : undefined)
      .then((s) => {
        if (!cancelled) setSources(s);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
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
        <h1>sources_trust</h1>
        {fleet.length > 0 && (
          <div className="control-bar">
            <label>
              agent
              <select value={agentRef} onChange={(e) => pickAgent(e.target.value)}>
                {fleet.map((a) => (
                  <option key={a.agent_id} value={a.agent_id}>
                    {a.agent_id}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        {!agentRef && <Empty hint="loading agent ref…" />}
        {agentRef && <AgentJson view="sources" id={agentRef} />}
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
      {fleet.length > 0 && (
        <div className="control-bar">
          <label>
            agent
            <select value={agentRef} onChange={(e) => pickAgent(e.target.value)}>
              <option value="">all agents</option>
              {fleet.map((a) => (
                <option key={a.agent_id} value={a.agent_id}>
                  {a.agent_id}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
      {!err && !sources && <p className="lede">loading…</p>}
      {sources && sources.length === 0 && (
        <Empty hint="no ingested sources — run a guarded session that retrieves content (e.g. scenario S1 with server up)" />
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
                <td>
                  <code>{s.agent_id ?? "—"}</code>
                </td>
                <td className="dim">
                  <code>{s.session_id ?? "—"}</code>
                </td>
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
