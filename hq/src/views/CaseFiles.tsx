import { useEffect, useMemo, useRef, useState } from "react";
import { api, type AgentVersionRow } from "../api";
import {
  cascadeReducer,
  emptyCascade,
  preferHeroSession,
  preferVersion,
  type CascadeState,
} from "../cascade";
import { AgentJson, Empty, Seam, ts } from "../components";
import type {
  AgentEnvelope,
  AgentModelRow,
  CascadeLink,
  FleetRow,
  Mode,
  SessionRow,
} from "../types";

type IncidentData = {
  goal: string | null;
  agent: { agent_id: string | null; name: string | null; role: string | null };
  exposure: string | null;
  scenario: string | null;
  root_cause: Record<string, unknown> | null;
  outcome: Record<string, unknown> | null;
  recommended_actions: string[];
  related_replay_id: string | null;
};

const HERO_SESSIONS = ["s_ecfdb55d", "s_2af44726"];

export function CaseFiles({
  mode,
  deepLink,
  onDeepLinkChange,
}: {
  mode: Mode;
  deepLink?: CascadeLink;
  onDeepLinkChange?: (next: CascadeLink) => void;
}) {
  const [fleet, setFleet] = useState<FleetRow[] | null>(null);
  const [cascade, setCascade] = useState<CascadeState>(() => ({
    ...emptyCascade(),
    agentId: deepLink?.agent ?? "",
    versionId: deepLink?.version ?? "",
    model: deepLink?.model ?? "",
    sessionId: deepLink?.session ?? "",
  }));
  const [versions, setVersions] = useState<AgentVersionRow[] | null>(null);
  const [models, setModels] = useState<AgentModelRow[]>([]);
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);
  const [versionHasNoPins, setVersionHasNoPins] = useState(false);
  const [envelope, setEnvelope] = useState<AgentEnvelope | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const prefer = useRef({
    version: deepLink?.version,
    model: deepLink?.model,
    session: deepLink?.session,
  });

  const { agentId, versionId, model, sessionId, lane } = cascade;

  useEffect(() => {
    if (!deepLink?.agent || deepLink.agent === agentId) return;
    prefer.current = {
      version: deepLink.version,
      model: deepLink.model,
      session: deepLink.session,
    };
    setCascade((s) => cascadeReducer(s, { type: "set_agent", agentId: deepLink.agent! }));
  }, [deepLink?.agent, deepLink?.version, deepLink?.model, deepLink?.session, agentId]);

  useEffect(() => {
    let cancelled = false;
    api
      .fleet()
      .then((f) => {
        if (cancelled) return;
        setFleet(f);
        if (f.length === 0) return;
        setCascade((cur) => {
          if (cur.agentId && f.some((a) => a.agent_id === cur.agentId)) return cur;
          const nextId =
            deepLink?.agent && f.some((a) => a.agent_id === deepLink.agent)
              ? deepLink.agent
              : f[0].agent_id;
          return cascadeReducer(cur, { type: "set_agent", agentId: nextId });
        });
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seed once from deepLink
  }, []);

  useEffect(() => {
    if (!agentId) {
      setVersions([]);
      setModels([]);
      return;
    }
    let cancelled = false;
    setSessions(null);
    Promise.all([api.agentVersions(agentId), api.agentModels(agentId)])
      .then(([vers, mods]) => {
        if (cancelled) return;
        setVersions(vers);
        setModels(mods);
        const wantV = prefer.current.version;
        const wantM = prefer.current.model;
        prefer.current.version = undefined;
        prefer.current.model = undefined;
        if (vers.length === 0) {
          const m =
            wantM && mods.some((r) => r.model === wantM) ? wantM : (mods[0]?.model ?? "");
          setCascade((s) => cascadeReducer(s, { type: "set_unversioned", model: m }));
          return;
        }
        const vid = preferVersion(
          vers.map((v) => v.version_id),
          wantV,
        );
        const row = vers.find((v) => v.version_id === vid);
        const nextModel =
          wantM && mods.some((r) => r.model === wantM)
            ? wantM
            : (row?.model ?? mods[0]?.model ?? "");
        setCascade((s) =>
          cascadeReducer(s, {
            type: "set_version",
            versionId: vid,
            model: nextModel || undefined,
          }),
        );
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  useEffect(() => {
    if (!agentId || !model) {
      setSessions([]);
      setCascade((s) => (s.sessionId ? cascadeReducer(s, { type: "set_session", sessionId: "" }) : s));
      return;
    }
    let cancelled = false;
    const params: {
      agent_id: string;
      model: string;
      agent_version?: string;
    } = { agent_id: agentId, model };
    if (lane === "versioned" && versionId) {
      params.agent_version = versionId;
    }
    api
      .sessions(params)
      .then(async (s) => {
        if (cancelled) return;
        let rows = s;
        let noPins = false;
        // Honest fallback: version exists but nothing pinned yet — show model sessions.
        if (rows.length === 0 && params.agent_version) {
          rows = await api.sessions({ agent_id: agentId, model });
          noPins = true;
        }
        if (cancelled) return;
        setVersionHasNoPins(noPins);
        setSessions(rows);
        const want = prefer.current.session;
        prefer.current.session = undefined;
        const next = preferHeroSession(
          rows.map((r) => r.session_id),
          HERO_SESSIONS,
          want,
        );
        setCascade((cur) => cascadeReducer(cur, { type: "set_session", sessionId: next }));
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, versionId, model, lane]);

  useEffect(() => {
    if (!sessionId) {
      setEnvelope(null);
      return;
    }
    let cancelled = false;
    setEnvelope(null);
    api
      .agentView("incident", sessionId)
      .then((e) => {
        if (!cancelled) setEnvelope(e);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    if (!onDeepLinkChange || !agentId) return;
    const next = {
      agent: agentId,
      version: versionId || undefined,
      model: model || undefined,
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
    model,
    sessionId,
    onDeepLinkChange,
    deepLink?.agent,
    deepLink?.version,
    deepLink?.model,
    deepLink?.session,
  ]);

  const agentOptions = useMemo(() => fleet ?? [], [fleet]);
  const selectedVersion = versions?.find((v) => v.version_id === versionId) ?? null;
  const modelOverride =
    selectedVersion?.model && model && selectedVersion.model !== model
      ? selectedVersion.model
      : null;

  if (mode === "agent") {
    if (sessionId) return <AgentJson view="incident" id={sessionId} />;
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>case_files</h1>
        <Empty hint="select agent → version → model → session in human_view, then toggle agent_view" />
      </>
    );
  }

  const data = (envelope?.data ?? null) as IncidentData | null;
  const rc = data?.root_cause ?? null;

  return (
    <>
      <p className="eyebrow">{"// improve"}</p>
      <h1>case_files</h1>
      <p className="lede">
        hand an incident to a coding agent: root cause · timeline · recommended actions ·
        fix-prompt with SigNoz MCP hints. pick agent → version → model → session, then export.
      </p>
      {err && <Seam error={err} />}
      {fleet && fleet.length === 0 && (
        <Empty hint="no agents yet — start the server and register agents via arcnet.init (or seed with ./scripts/run-demo.sh)" />
      )}

      {agentOptions.length > 0 && (
        <div className="control-bar">
          <label>
            agent
            <select
              value={agentId}
              onChange={(e) => {
                prefer.current = { version: undefined, model: undefined, session: undefined };
                setCascade((s) => cascadeReducer(s, { type: "set_agent", agentId: e.target.value }));
              }}
            >
              {agentOptions.map((a) => (
                <option key={a.agent_id} value={a.agent_id}>
                  {a.agent_id}
                  {a.model ? ` · fleet:${a.model}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            version
            <select
              value={lane === "unversioned" ? "__unversioned__" : versionId}
              onChange={(e) => {
                prefer.current.session = undefined;
                const v = e.target.value;
                if (v === "__unversioned__") {
                  setCascade((s) =>
                    cascadeReducer(s, {
                      type: "set_unversioned",
                      model: models[0]?.model ?? s.model,
                    }),
                  );
                  return;
                }
                const row = (versions ?? []).find((x) => x.version_id === v);
                setCascade((s) =>
                  cascadeReducer(s, {
                    type: "set_version",
                    versionId: v,
                    model: row?.model ?? undefined,
                  }),
                );
              }}
              disabled={versions === null}
            >
              {versions && versions.length === 0 && (
                <option value="__unversioned__">unversioned / observed models</option>
              )}
              {(versions ?? []).map((v) => (
                <option key={v.version_id} value={v.version_id}>
                  {v.version} · {v.model ?? "—"} · {v.version_id}
                </option>
              ))}
              {versions && versions.length > 0 && (
                <option value="__unversioned__">unversioned / observed models</option>
              )}
            </select>
          </label>
          <label>
            model
            <select
              value={model}
              onChange={(e) => {
                prefer.current.session = undefined;
                setCascade((s) => cascadeReducer(s, { type: "set_model", model: e.target.value }));
              }}
              disabled={models.length === 0 && !model}
            >
              {models.length === 0 && !model && <option value="">no sessions for agent</option>}
              {model && !models.some((m) => m.model === model) && (
                <option value={model}>{model} · from version</option>
              )}
              {models.map((m) => (
                <option key={m.model} value={m.model}>
                  {m.model} · {m.session_count} session{m.session_count === 1 ? "" : "s"}
                </option>
              ))}
            </select>
          </label>
          <label>
            session
            <select
              value={sessionId}
              onChange={(e) =>
                setCascade((s) => cascadeReducer(s, { type: "set_session", sessionId: e.target.value }))
              }
              disabled={!sessions || sessions.length === 0}
            >
              {sessions && sessions.length === 0 && <option value="">no sessions</option>}
              {(sessions ?? []).map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {s.session_id} · {s.scenario ?? "—"} · {s.status}
                  {s.agent_version ? ` · ver:${s.agent_version}` : ""} · {ts(s.started_at)}
                </option>
              ))}
            </select>
          </label>
          {sessionId && (
            <a className="btn" href={api.caseFileUrl(sessionId)} download>
              export_case_file()
            </a>
          )}
          {sessionId && (
            <a
              className="btn ghost"
              href={`#hq_agent?agent=${encodeURIComponent(agentId)}&version=${encodeURIComponent(versionId)}&session=${encodeURIComponent(sessionId)}`}
            >
              hq_agent · pin session
            </a>
          )}
        </div>
      )}

      {lane === "unversioned" && agentId && (
        <p className="dim">
          lane=unversioned — no registry pin filter; showing sessions by observed model only.
        </p>
      )}
      {versionHasNoPins && lane === "versioned" && (
        <p className="dim">
          no sessions pinned to this version yet — showing unpinned sessions for model={model}{" "}
          (apply-model + session pin links them).
        </p>
      )}
      {modelOverride && (
        <p className="dim">
          warning: model override ({model}) ≠ version registry model ({modelOverride})
        </p>
      )}

      {versions && versions.length === 0 && agentId && (
        <Empty hint="no registered versions — seed_demo / register_agent_version, or use unversioned observed models" />
      )}
      {sessions && sessions.length === 0 && agentId && model && (
        <Empty hint="no sessions for this agent + version/model — pick another version or run a scenario" />
      )}
      {err && !fleet && (
        <Empty hint="could not load fleet — is arcnet-server up on :8000?" />
      )}

      {versions && versions.length > 0 && (
        <>
          <p className="eyebrow">{"// version_timeline"}</p>
          <div className="history">
            {versions.map((v) => (
              <button
                key={v.version_id}
                type="button"
                className={`history-row ${versionId === v.version_id ? "active" : ""}`}
                onClick={() => {
                  prefer.current.session = undefined;
                  setCascade((s) =>
                    cascadeReducer(s, {
                      type: "set_version",
                      versionId: v.version_id,
                      model: v.model ?? undefined,
                    }),
                  );
                }}
              >
                {ts(v.created_at)} · {v.version} · {v.model ?? "—"}
                {v.source_ref ? ` · ${v.source_ref}` : ""}
              </button>
            ))}
          </div>
        </>
      )}

      {data && (
        <div className="casefile">
          <div className="col">
            <h3>incident</h3>
            <div className="stat-row">
              <span>scenario</span>
              <span>{data.scenario ?? "—"}</span>
            </div>
            <div className="stat-row">
              <span>agent</span>
              <span>
                {data.agent?.agent_id ?? "—"} ({data.agent?.role ?? "—"})
              </span>
            </div>
            <div className="stat-row">
              <span>agent_version</span>
              <span>
                {(sessions ?? []).find((s) => s.session_id === sessionId)?.agent_version ??
                  "— unpinned"}
              </span>
            </div>
            <div className="stat-row">
              <span>exposure</span>
              <span>{data.exposure ?? "—"}</span>
            </div>
            <div className="stat-row">
              <span>goal</span>
              <span className="wrap">{data.goal ?? "—"}</span>
            </div>
            <div className="stat-row">
              <span>outcome</span>
              <span className="wrap">{JSON.stringify(data.outcome)}</span>
            </div>
            <div className="stat-row">
              <span>related_replay</span>
              <span>{data.related_replay_id ?? "—"}</span>
            </div>
          </div>
          <div className={`col ${rc ? "exploited" : ""}`}>
            <h3>root_cause</h3>
            {!rc && <p className="step">no guard finding — clean run.</p>}
            {rc && (
              <>
                {(
                  [
                    "checkpoint",
                    "action",
                    "trust_level",
                    "category",
                    "subcategory",
                    "risk_score",
                  ] as const
                ).map((k) => (
                  <div className="stat-row" key={k}>
                    <span>{k}</span>
                    <span>{String(rc[k] ?? "—")}</span>
                  </div>
                ))}
                <p className="step evidence">{String(rc.evidence_excerpt ?? "")}</p>
              </>
            )}
          </div>
          <div className="col resisted">
            <h3>recommended_actions</h3>
            {(data.recommended_actions ?? []).map((a, i) => (
              <p className="step" key={i}>
                {i + 1}. {a}
              </p>
            ))}
            <p className="step dim">{envelope?.hints?.raw_evidence ?? ""}</p>
          </div>
        </div>
      )}
    </>
  );
}
