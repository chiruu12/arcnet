import { useEffect, useState } from "react";
import { api, type AgentVersionRow } from "../api";
import { Empty, Seam, ts } from "../components";
import type { SignalRow } from "../types";

const RUN_HINT =
  'PYTHONPATH=sdk:agents uv run python -m hq_agent "fleet health + griffin MAD + proposals"';

/** Pull trailing model id from proposal guidance like "…: gpt-4o-mini → gpt-4o." */
function parseProposedModel(guidance: string | null): string {
  if (!guidance) return "";
  const m = guidance.match(/→\s*([A-Za-z0-9._-]+)|:\s*([A-Za-z0-9._-]+)\./);
  return (m?.[1] || m?.[2] || "").trim();
}

function formatApplyError(e: unknown): string {
  const raw = String(e);
  if (raw.includes("Failed to fetch") || raw.includes("NetworkError")) {
    return "apply failed — arcnet-server unreachable (is :8000 up?)";
  }
  if (raw.includes("400")) {
    return `apply rejected — ${raw.slice(0, 280)}`;
  }
  return `apply failed — ${raw.slice(0, 280)}`;
}

export function HqAgent({
  deepLink,
}: {
  deepLink?: { agent?: string; session?: string };
}) {
  const [proposals, setProposals] = useState<SignalRow[] | null>(null);
  const [versions, setVersions] = useState<AgentVersionRow[] | null>(null);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [agentId, setAgentId] = useState(deepLink?.agent ?? "agent_j");
  const [sessionId, setSessionId] = useState(deepLink?.session ?? "");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [applyModel, setApplyModel] = useState("");
  const [applyVersion, setApplyVersion] = useState("");
  const [applyConfirm, setApplyConfirm] = useState(false);
  const [applyProposalId, setApplyProposalId] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (deepLink?.agent && deepLink.agent !== agentId) {
      setAgentId(deepLink.agent);
    }
    if (deepLink?.session != null && deepLink.session !== sessionId) {
      setSessionId(deepLink.session);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to deep-link changes
  }, [deepLink?.agent, deepLink?.session]);

  useEffect(() => {
    let cancelled = false;
    setProposals(null);
    setVersions(null);
    Promise.all([
      api.signals({ agent_id: agentId, source: "hq_agent", limit: 40 }),
      api.agentVersionTimeline(agentId),
    ])
      .then(([sigs, tl]) => {
        if (cancelled) return;
        setProposals(sigs);
        setVersions(tl.versions);
        setCurrentModel(tl.current_model);
        setErr(null);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          const msg = String(e);
          setErr(
            msg.includes("Failed to fetch")
              ? "arcnet-server unreachable — start uvicorn on :8000 and refresh"
              : msg,
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, tick]);

  function refresh() {
    setFlash(null);
    setTick((n) => n + 1);
  }

  function prepApply(p: SignalRow) {
    const model = parseProposedModel(p.guidance);
    setApplyModel(model);
    setApplyProposalId(p.signal_id);
    setApplyConfirm(false);
    if (p.session_id && !sessionId) {
      setSessionId(p.session_id);
    }
    if (!applyVersion) {
      const d = new Date();
      const stamp = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}.${d.getUTCHours()}${d.getUTCMinutes()}`;
      setApplyVersion(stamp);
    }
  }

  async function submitApply() {
    if (!applyConfirm) {
      setFlash("check confirm — apply is human-gated");
      return;
    }
    if (!applyModel.trim() || !applyVersion.trim()) {
      setFlash("model and version required");
      return;
    }
    setBusy(true);
    setFlash(null);
    try {
      const out = await api.applyModel(agentId, {
        confirm: true,
        model: applyModel.trim(),
        version: applyVersion.trim(),
        proposal_signal_id: applyProposalId ?? undefined,
        session_id: sessionId.trim() || undefined,
        notes: sessionId.trim()
          ? `applied from HQ proposal inbox; pinned session ${sessionId.trim()}`
          : "applied from HQ proposal inbox",
      });
      const pinNote = sessionId.trim() ? ` · pinned ${sessionId.trim()}` : "";
      setFlash(`applied ${out.model} as ${out.version.version}${pinNote}`);
      setApplyConfirm(false);
      setApplyProposalId(null);
      refresh();
    } catch (e: unknown) {
      setFlash(formatApplyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <p className="eyebrow">{"// improve"}</p>
      <h1>hq_agent</h1>
      <p className="lede">
        operator maintenance layer — proposal inbox + version timeline. griffin ={" "}
        <code>MAD</code> (not TabFM). apply requires explicit confirm (no silent swaps). optional
        session_id pins the incident that justified the change.
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
        <label>
          session_id (pin)
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value.trim())}
            placeholder="optional — from case_files"
            spellCheck={false}
          />
        </label>
        <button type="button" className="btn" onClick={refresh} disabled={busy}>
          refresh
        </button>
        <a className="btn ghost" href={`#case_files?agent=${encodeURIComponent(agentId)}`}>
          case_files
        </a>
        {currentModel && (
          <span className="dim">
            current_model=<code>{currentModel}</code>
          </span>
        )}
      </div>

      <p className="eyebrow">{"// run locally"}</p>
      <pre className="agent-json">{RUN_HINT}</pre>

      {err && <Seam error={err} />}
      {flash && <p className={flash.startsWith("apply failed") || flash.startsWith("apply rejected") ? "err" : "lede"}>{flash}</p>}

      <p className="eyebrow">{"// apply_model (human-gated)"}</p>
      <div className="control-bar">
        <label>
          model
          <input
            value={applyModel}
            onChange={(e) => setApplyModel(e.target.value)}
            placeholder="gpt-4o"
            spellCheck={false}
          />
        </label>
        <label>
          version
          <input
            value={applyVersion}
            onChange={(e) => setApplyVersion(e.target.value)}
            placeholder="2026-07-22.1"
            spellCheck={false}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={applyConfirm}
            onChange={(e) => setApplyConfirm(e.target.checked)}
          />
          confirm
        </label>
        <button type="button" className="btn" onClick={submitApply} disabled={busy}>
          apply
        </button>
      </div>

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
              <th></th>
            </tr>
          </thead>
          <tbody>
            {proposals.map((p) => (
              <tr key={p.signal_id}>
                <td className="dim">{ts(p.created_at)}</td>
                <td className="wrap">{p.reason}</td>
                <td className="dim wrap">{p.guidance ?? "—"}</td>
                <td>{p.status}</td>
                <td>
                  {p.status !== "applied" && (
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={() => prepApply(p)}
                      disabled={busy}
                    >
                      prep_apply
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="eyebrow">{"// agent_versions"}</p>
      {versions === null && !err && <p className="lede">loading…</p>}
      {versions && versions.length === 0 && (
        <Empty hint="no registered versions — register_agent_version or apply-model after a deploy" />
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
