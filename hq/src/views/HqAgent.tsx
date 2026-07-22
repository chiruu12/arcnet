import { useEffect, useState } from "react";
import { api, type AgentVersionRow } from "../api";
import { Empty, Seam, ts } from "../components";
import type { SignalRow } from "../types";

const RUN_HINT =
  'PYTHONPATH=sdk:agents uv run python -m hq_agent "fleet health + griffin MAD + proposals"';

export function HqAgent() {
  const [proposals, setProposals] = useState<SignalRow[] | null>(null);
  const [versions, setVersions] = useState<AgentVersionRow[] | null>(null);
  const [agentId, setAgentId] = useState("agent_j");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setProposals(null);
    setVersions(null);
    Promise.all([
      api.signals({ agent_id: agentId, limit: 40 }),
      api.agentVersions(agentId),
    ])
      .then(([sigs, vers]) => {
        if (cancelled) return;
        setProposals(sigs.filter((s) => s.source === "hq_agent"));
        setVersions(vers);
        setErr(null);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  return (
    <>
      <p className="eyebrow">{"// improve"}</p>
      <h1>hq_agent</h1>
      <p className="lede">
        operator maintenance layer — proposals + version timeline. griffin ={" "}
        <code>MAD</code> (not TabFM). model changes are proposals only.
      </p>

      <div className="control-bar">
        <label>
          agent_id
          <input
            value={agentId}
            onChange={(e) => setAgentId(e.target.value.trim() || "agent_j")}
            spellCheck={false}
          />
        </label>
      </div>

      <p className="eyebrow">{"// run locally"}</p>
      <pre className="agent-json">{RUN_HINT}</pre>

      {err && <Seam error={err} />}

      <p className="eyebrow">{"// model_proposals"}</p>
      {proposals === null && !err && <p className="lede">loading…</p>}
      {proposals && proposals.length === 0 && (
        <Empty hint="no hq_agent proposals — run the agent or call propose_model_change" />
      )}
      {proposals && proposals.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>time</th>
              <th>reason</th>
              <th>guidance</th>
              <th>status</th>
            </tr>
          </thead>
          <tbody>
            {proposals.map((p) => (
              <tr key={p.signal_id}>
                <td className="dim">{ts(p.created_at)}</td>
                <td className="wrap">{p.reason}</td>
                <td className="wrap dim">{p.guidance ?? "—"}</td>
                <td>{p.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="eyebrow">{"// agent_versions"}</p>
      {versions === null && !err && <p className="lede">loading…</p>}
      {versions && versions.length === 0 && (
        <Empty hint="no registered versions — register_agent_version after a deploy" />
      )}
      {versions && versions.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>time</th>
              <th>version</th>
              <th>model</th>
              <th>source_ref</th>
              <th>notes</th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.version_id}>
                <td className="dim">{ts(v.created_at)}</td>
                <td>{v.version}</td>
                <td>
                  {v.model ?? "—"}
                  {v.model_version ? ` @ ${v.model_version}` : ""}
                </td>
                <td className="dim wrap">{v.source_ref ?? "—"}</td>
                <td className="dim wrap">{v.notes ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
