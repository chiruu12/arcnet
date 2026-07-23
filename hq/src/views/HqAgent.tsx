import { useEffect, useRef, useState } from "react";
import { api, type AgentVersionRow } from "../api";
import { cascadeReducer, emptyCascade, type CascadeState } from "../cascade";
import { Empty, Seam, ts } from "../components";
import { formatCostDelta } from "../modelIntel";
import { showingOfTotal } from "../pageLabel";
import type { AgentModelsResponse, CascadeLink, SignalRow } from "../types";

const RUN_HINT =
  'PYTHONPATH=sdk:agents uv run python -m hq_agent "fleet health + griffin MAD + proposals"';

const PROPOSALS_PAGE = 40;
const VERSIONS_PAGE = 50;

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
  onDeepLinkChange,
}: {
  deepLink?: CascadeLink;
  onDeepLinkChange?: (next: CascadeLink) => void;
}) {
  const [cascade, setCascade] = useState<CascadeState>(() => ({
    ...emptyCascade(),
    agentId: deepLink?.agent ?? "agent_j",
    versionId: deepLink?.version ?? "",
    model: deepLink?.model ?? "",
    sessionId: deepLink?.session ?? "",
  }));
  const [proposals, setProposals] = useState<SignalRow[] | null>(null);
  const [proposalsTotal, setProposalsTotal] = useState(0);
  const [versions, setVersions] = useState<AgentVersionRow[] | null>(null);
  const [versionsTotal, setVersionsTotal] = useState(0);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [modelIntel, setModelIntel] = useState<AgentModelsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [applyModel, setApplyModel] = useState("");
  const [applyVersion, setApplyVersion] = useState("");
  const [applySourceRef, setApplySourceRef] = useState("");
  const [applyConfirm, setApplyConfirm] = useState(false);
  const [pinSessionRequired, setPinSessionRequired] = useState(true);
  const [applyProposalId, setApplyProposalId] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [reloadBanner, setReloadBanner] = useState<string | null>(null);
  const [pinpoint, setPinpoint] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const prefer = useRef({
    version: deepLink?.version,
    model: deepLink?.model,
    session: deepLink?.session,
  });

  const { agentId, versionId, sessionId } = cascade;

  useEffect(() => {
    if (!deepLink) return;
    prefer.current = {
      version: deepLink.version,
      model: deepLink.model,
      session: deepLink.session,
    };
    if (deepLink.agent && deepLink.agent !== agentId) {
      setCascade((s) => cascadeReducer(s, { type: "set_agent", agentId: deepLink.agent! }));
      return;
    }
    setCascade((s) => {
      let next = s;
      if (deepLink.version != null && deepLink.version !== s.versionId) {
        next = cascadeReducer(next, {
          type: "set_version",
          versionId: deepLink.version,
          // Clear stale model when link omits it; timeline/row fill happens next.
          model: deepLink.model !== undefined ? deepLink.model : "",
        });
      } else if (
        deepLink.version != null &&
        deepLink.model !== undefined &&
        deepLink.model !== s.model
      ) {
        next = cascadeReducer(next, { type: "set_model", model: deepLink.model });
      }
      if (deepLink.session != null && deepLink.session !== next.sessionId) {
        next = cascadeReducer(next, { type: "set_session", sessionId: deepLink.session });
      }
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to deep-link changes
  }, [deepLink?.agent, deepLink?.session, deepLink?.version, deepLink?.model]);

  useEffect(() => {
    let cancelled = false;
    setProposals(null);
    setVersions(null);
    setModelIntel(null);
    Promise.all([
      api.signalsPage({ agent_id: agentId, source: "hq_agent", limit: PROPOSALS_PAGE }),
      api.agentVersionTimeline(agentId),
      api.agentVersionsPage(agentId, { limit: VERSIONS_PAGE }),
      api.agentModelsIntel(agentId),
    ])
      .then(([sigs, tl, versPage, intel]) => {
        if (cancelled) return;
        setProposals(sigs.rows);
        setProposalsTotal(sigs.total);
        setVersions(versPage.rows);
        setVersionsTotal(versPage.total);
        setModelIntel(intel);
        setCurrentModel(tl.current_model);
        setErr(null);
        const wantV = prefer.current.version;
        const wantM = prefer.current.model;
        prefer.current.version = undefined;
        prefer.current.model = undefined;
        const versionRows = versPage.rows.length > 0 ? versPage.rows : tl.versions;
        setCascade((s) => {
          if (wantV && versionRows.some((v) => v.version_id === wantV)) {
            const row = versionRows.find((v) => v.version_id === wantV)!;
            return cascadeReducer(s, {
              type: "set_version",
              versionId: wantV,
              model: wantM !== undefined ? wantM : (row.model ?? ""),
            });
          }
          if (s.versionId) {
            // Deep link / user already chose — do not overwrite with newest.
            if (!s.model) {
              const row = versionRows.find((v) => v.version_id === s.versionId);
              if (row?.model) {
                return cascadeReducer(s, {
                  type: "hydrate",
                  partial: { model: row.model },
                });
              }
            }
            return s;
          }
          if (versionRows[0]) {
            return cascadeReducer(s, {
              type: "set_version",
              versionId: versionRows[0].version_id,
              model: versionRows[0].model ?? "",
            });
          }
          return s;
        });
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh on agent/tick only
  }, [agentId, tick]);

  useEffect(() => {
    if (!onDeepLinkChange || !agentId) return;
    const next = {
      agent: agentId,
      version: versionId || undefined,
      model: cascade.model || undefined,
      session: sessionId || undefined,
    };
    if (
      deepLink?.agent === next.agent &&
      deepLink?.version === next.version &&
      deepLink?.model === next.model &&
      deepLink?.session === next.session
    ) {
      return;
    }
    onDeepLinkChange(next);
  }, [
    agentId,
    versionId,
    cascade.model,
    sessionId,
    onDeepLinkChange,
    deepLink?.agent,
    deepLink?.version,
    deepLink?.model,
    deepLink?.session,
  ]);

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
      setCascade((s) => cascadeReducer(s, { type: "set_session", sessionId: p.session_id! }));
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
    if (pinSessionRequired && !sessionId.trim()) {
      setFlash("session_id required for pin path — uncheck pin_session or pick a session");
      return;
    }
    setBusy(true);
    setFlash(null);
    setPinpoint(null);
    try {
      const out = await api.applyModel(agentId, {
        confirm: true,
        model: applyModel.trim(),
        version: applyVersion.trim(),
        source_ref: applySourceRef.trim() || undefined,
        proposal_signal_id: applyProposalId ?? undefined,
        session_id: sessionId.trim() || undefined,
        notes: sessionId.trim()
          ? `applied from HQ proposal inbox; pinned session ${sessionId.trim()}`
          : "applied from HQ proposal inbox",
      });
      const pinNote = sessionId.trim() ? ` · pinned ${sessionId.trim()}` : "";
      setFlash(`applied ${out.model} as ${out.version.version}${pinNote}`);
      if (out.agentos_reload_required) {
        const probeNote = out.agentos_probe?.note ? ` — ${out.agentos_probe.note}` : "";
        setReloadBanner(
          (out.agentos_reload_instructions ||
            "AgentOS still on old model until restart — SQLite updated; do not auto-restart from server.") +
            probeNote,
        );
      } else {
        setReloadBanner(
          out.agentos_reload_instructions ||
            out.agentos_probe?.note ||
            "SQLite and AgentOS model already match — no restart needed.",
        );
      }
      setApplyConfirm(false);
      setApplyProposalId(null);
      setCascade((s) =>
        cascadeReducer(s, {
          type: "set_version",
          versionId: out.version.version_id,
          model: out.model,
        }),
      );
      if (sessionId.trim()) {
        try {
          const check = await api.agentView("check", sessionId.trim());
          const data = check.data as { version_pinpoint?: { narrative?: string } };
          const narrative = data?.version_pinpoint?.narrative;
          if (narrative) setPinpoint(narrative);
        } catch {
          /* pinpoint optional */
        }
      }
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
        operator maintenance layer — diagnose strip (agent → version → session) + proposal inbox +
        version timeline. griffin = <code>MAD</code> (not TabFM). apply requires explicit confirm.
        pin_session path requires session_id; optional source_ref records provenance. apply updates
        SQLite only — AgentOS reload is manual.
      </p>

      {reloadBanner && (
        <p className="err" role="status">
          agentos_reload_required: {reloadBanner}{" "}
          <button type="button" className="btn ghost" onClick={() => setReloadBanner(null)}>
            dismiss
          </button>
        </p>
      )}
      {pinpoint && (
        <p className="lede" role="status">
          version_pinpoint: {pinpoint}
        </p>
      )}

      <div className="control-bar">
        <label>
          agent_id
          <input
            value={agentId}
            onChange={(e) =>
              setCascade((s) =>
                cascadeReducer(s, { type: "set_agent", agentId: e.target.value.trim() || "agent_j" }),
              )
            }
            spellCheck={false}
          />
        </label>
        <label>
          version
          <select
            value={versionId}
            onChange={(e) => {
              const row = (versions ?? []).find((v) => v.version_id === e.target.value);
              setCascade((s) =>
                cascadeReducer(s, {
                  type: "set_version",
                  versionId: e.target.value,
                  model: row?.model ?? undefined,
                }),
              );
            }}
          >
            <option value="">—</option>
            {(versions ?? []).map((v) => (
              <option key={v.version_id} value={v.version_id}>
                {v.version} · {v.model ?? "—"}
              </option>
            ))}
          </select>
        </label>
        <label>
          session_id (pin)
          <input
            value={sessionId}
            onChange={(e) =>
              setCascade((s) =>
                cascadeReducer(s, { type: "set_session", sessionId: e.target.value.trim() }),
              )
            }
            placeholder={pinSessionRequired ? "required when pin_session checked" : "optional"}
            spellCheck={false}
          />
        </label>
        <button type="button" className="btn" onClick={refresh} disabled={busy}>
          refresh
        </button>
        <a
          className="btn ghost"
          href={`#case_files?agent=${encodeURIComponent(agentId)}${versionId ? `&version=${encodeURIComponent(versionId)}` : ""}${sessionId ? `&session=${encodeURIComponent(sessionId)}` : ""}`}
        >
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
      {flash && (
        <p
          className={
            flash.startsWith("apply failed") || flash.startsWith("apply rejected") ? "err" : "lede"
          }
        >
          {flash}
        </p>
      )}

      <p className="eyebrow">{"// models (catalog projections)"}</p>
      {modelIntel === null && !err && <p className="lede">loading…</p>}
      {modelIntel && (
        <>
          <p className="dim" role="status">
            catalog={modelIntel.catalog_version || "—"} ·{" "}
            {modelIntel.price_label || "list-price estimate"} · usage_tokens=
            {modelIntel.usage_evidence.total_tokens} (
            {modelIntel.usage_evidence.session_count} sessions)
          </p>
          {modelIntel.reasoning_recommendation && (
            <p className="lede">
              reasoning_rec: <code>{modelIntel.reasoning_recommendation.model_id}</code> (
              {modelIntel.reasoning_recommendation.tier}) —{" "}
              {modelIntel.reasoning_recommendation.rationale}
            </p>
          )}
          {modelIntel.candidates.length === 0 ? (
            <Empty hint="no catalog candidates" />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>model</th>
                  <th>tier</th>
                  <th>Δ cost</th>
                  <th>strengths</th>
                </tr>
              </thead>
              <tbody>
                {modelIntel.candidates.slice(0, 12).map((c) => (
                  <tr key={c.id}>
                    <td>
                      {c.id}
                      {c.is_current ? " · current" : ""}
                      {c.reasoning ? " · reasoning" : ""}
                    </td>
                    <td className="dim">{c.tier}</td>
                    <td className="dim">{formatCostDelta(c.projected_cost_delta)}</td>
                    <td className="dim wrap">{c.strengths}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

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
        <label>
          source_ref
          <input
            value={applySourceRef}
            onChange={(e) => setApplySourceRef(e.target.value)}
            placeholder="git sha / prompt path"
            spellCheck={false}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={pinSessionRequired}
            onChange={(e) => setPinSessionRequired(e.target.checked)}
          />
          pin_session
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
        <>
          <p className="dim" role="status">
            {showingOfTotal(proposals.length, proposalsTotal)}
          </p>
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
        </>
      )}

      <p className="eyebrow">{"// agent_versions"}</p>
      {versions === null && !err && <p className="lede">loading…</p>}
      {versions && versions.length === 0 && (
        <Empty hint="no registered versions — register_agent_version or apply-model after a deploy" />
      )}
      {versions && versions.length > 0 && (
        <>
          <p className="dim" role="status">
            {showingOfTotal(versions.length, versionsTotal)}
          </p>
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
                <tr
                  key={v.version_id}
                  className={versionId === v.version_id ? "active" : undefined}
                  onClick={() =>
                    setCascade((s) =>
                      cascadeReducer(s, {
                        type: "set_version",
                        versionId: v.version_id,
                        model: v.model ?? undefined,
                      }),
                    )
                  }
                  style={{ cursor: "pointer" }}
                >
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
        </>
      )}
    </>
  );
}
