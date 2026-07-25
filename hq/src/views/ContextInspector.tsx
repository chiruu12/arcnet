import { useEffect, useMemo, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import { api, toUserError, type AgentVersionRow } from "../api";
import {
  buildContextInspectorTwin,
  buildIngestTimeline,
  ingestSummary,
  parseAgentThreats,
  unlinkedThreats,
  type AgentThreatRow,
} from "../contextInspector";
import {
  cascadeReducer,
  emptyCascade,
  preferHeroSession,
  preferVersion,
  type CascadeState,
} from "../cascade";
import { Empty, ViewSeam, ts } from "../components";
import { showingOfTotal } from "../pageLabel";
import { useRetryToken } from "../viewRetry";
import type { AgentModelRow, CascadeLink, FleetRow, Mode, SessionRow, SourceRow } from "../types";

const HERO_SESSIONS = ["s_ecfdb55d", "s_2af44726"];

const ACTION_CLASS: Record<string, string> = {
  block: "danger",
  redact: "warn",
  review: "warn",
  allow: "ok",
};

function ContextInspectorTwin({ sessionId }: { sessionId: string }) {
  const [twin, setTwin] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [retryAt, retry] = useRetryToken();

  useEffect(() => {
    let cancelled = false;
    setTwin(null);
    setErr(null);
    Promise.all([
      api.sources({ session_id: sessionId }),
      api.agentView("threats", sessionId),
    ])
      .then(([sources, threatsEnv]) => {
        if (cancelled) return;
        const threats = parseAgentThreats(threatsEnv.data);
        setTwin(
          buildContextInspectorTwin(sessionId, sources, threats, threatsEnv.links),
        );
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(toUserError(e));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, retryAt]);

  return (
    <>
      <p className="eyebrow">{"// agent_view"}</p>
      <h1>
        GET /api/agent-view/context_inspector/{sessionId}
      </h1>
      <p className="dim step">
        composed twin — merges /api/sources?session_id=… and /api/agent-view/threats/…
      </p>
      {err && <ViewSeam error={err} onRetry={retry} />}
      {!err && !twin && <p className="lede">loading…</p>}
      {twin && <pre className="agent-json">{JSON.stringify(twin, null, 2)}</pre>}
    </>
  );
}

export function ContextInspector({
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
  const [sessionsTotal, setSessionsTotal] = useState(0);
  const [versionHasNoPins, setVersionHasNoPins] = useState(false);
  const [sources, setSources] = useState<SourceRow[] | null>(null);
  const [threats, setThreats] = useState<AgentThreatRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [retryAt, retry] = useRetryToken();
  const prefer = useRef({
    version: deepLink?.version,
    model: deepLink?.model,
    session: deepLink?.session,
  });

  const { agentId, versionId, model, sessionId, lane } = cascade;

  useEffect(() => {
    if (!deepLink?.agent) return;
    prefer.current = {
      version: deepLink.version,
      model: deepLink.model,
      session: deepLink.session,
    };
    if (deepLink.agent !== agentId) {
      setCascade((s) => cascadeReducer(s, { type: "set_agent", agentId: deepLink.agent! }));
      return;
    }
    setCascade((s) => {
      let next = s;
      const wantV = deepLink.version ?? "";
      const wantM = deepLink.model;
      if (wantV && (wantV !== s.versionId || (wantM !== undefined && wantM !== s.model))) {
        const row = (versions ?? []).find((v) => v.version_id === wantV);
        next = cascadeReducer(next, {
          type: "set_version",
          versionId: wantV,
          model: wantM !== undefined ? wantM : (row?.model ?? ""),
        });
      } else if (!wantV && wantM !== undefined && wantM !== s.model) {
        next = cascadeReducer(next, { type: "set_unversioned", model: wantM });
      } else if (wantM !== undefined && wantM !== next.model && wantV === next.versionId) {
        next = cascadeReducer(next, { type: "set_model", model: wantM });
      }
      const wantS = deepLink.session ?? "";
      if (wantS !== next.sessionId) {
        next = cascadeReducer(next, { type: "set_session", sessionId: wantS });
      }
      return next;
    });
  }, [deepLink?.agent, deepLink?.version, deepLink?.model, deepLink?.session, agentId, versions]);

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
        if (!cancelled) setErr(toUserError(e));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retryAt]);

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
        if (!cancelled) setErr(toUserError(e));
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, retryAt]);

  useEffect(() => {
    if (!agentId || !model) {
      setSessions([]);
      setSessionsTotal(0);
      setCascade((s) => (s.sessionId ? cascadeReducer(s, { type: "set_session", sessionId: "" }) : s));
      return;
    }
    let cancelled = false;
    const params: { agent_id: string; model: string; agent_version?: string } = {
      agent_id: agentId,
      model,
    };
    if (lane === "versioned" && versionId) {
      params.agent_version = versionId;
    }
    api
      .sessions(params)
      .then(async (s) => {
        if (cancelled) return;
        let rows = s;
        let noPins = false;
        if (rows.length === 0 && params.agent_version) {
          rows = await api.sessions({ agent_id: agentId, model });
          noPins = true;
        }
        if (cancelled) return;
        setVersionHasNoPins(noPins);
        setSessions(rows);
        setSessionsTotal(rows.length);
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
        if (!cancelled) setErr(toUserError(e));
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, versionId, model, lane, retryAt]);

  useEffect(() => {
    if (!sessionId) {
      setSources(null);
      setThreats(null);
      return;
    }
    let cancelled = false;
    setSources(null);
    setThreats(null);
    Promise.all([
      api.sources({ session_id: sessionId }),
      api.agentView("threats", sessionId),
    ])
      .then(([srcRows, threatsEnv]) => {
        if (cancelled) return;
        setSources(srcRows);
        setThreats(parseAgentThreats(threatsEnv.data));
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(toUserError(e));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, retryAt]);

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
  const timeline = useMemo(
    () => (sources && threats ? buildIngestTimeline(sources, threats) : []),
    [sources, threats],
  );
  const summary = useMemo(
    () => (sources && threats ? ingestSummary(sources, threats) : null),
    [sources, threats],
  );
  const orphans = useMemo(
    () => (sources && threats ? unlinkedThreats(sources, threats) : []),
    [sources, threats],
  );

  if (mode === "agent") {
    if (sessionId) return <ContextInspectorTwin sessionId={sessionId} />;
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>context_inspector</h1>
        <Empty hint="select agent → version → model → session in human_view, then toggle agent_view" />
      </>
    );
  }

  return (
    <>
      <p className="eyebrow">{"// observe"}</p>
      <h1>context_inspector</h1>
      <p className="lede">
        per-session ingest ledger · trust at ingest checkpoint · provenance to downstream threats.
      </p>
      {err && <ViewSeam error={err} onRetry={retry} />}
      {fleet && fleet.length === 0 && (
        <Empty hint="no agents yet — start the server and register agents via arcnet.init (or seed with ./scripts/run-demo.sh)" />
      )}

      {agentOptions.length > 0 && (
        <CascadeControlBar
          agentId={agentId}
          versionId={versionId}
          model={model}
          sessionId={sessionId}
          lane={lane}
          versions={versions}
          models={models}
          sessions={sessions}
          sessionsTotal={sessionsTotal}
          agentOptions={agentOptions}
          prefer={prefer}
          setCascade={setCascade}
        />
      )}

      {lane === "unversioned" && agentId && (
        <p className="dim">
          lane=unversioned — no registry pin filter; showing sessions by observed model only.
        </p>
      )}
      {versionHasNoPins && lane === "versioned" && (
        <p className="dim">
          no sessions pinned to this version yet — showing unpinned sessions for model={model}.
        </p>
      )}

      {sessions && sessions.length === 0 && agentId && model && (
        <Empty hint="no sessions for this agent + version/model — pick another version or run a scenario" />
      )}

      {sessionId && !sources && !err && <p className="lede">loading ingest ledger…</p>}

      {summary && sources && (
        <InspectorSummary summary={summary} sessionId={sessionId} />
      )}

      {timeline.length > 0 && (
        <>
          <p className="eyebrow">{"// ingest_timeline"}</p>
          <IngestTimelineView timeline={timeline} />
        </>
      )}

      {sources && sources.length === 0 && sessionId && (
        <Empty hint="no ingested sources for this session — run a guarded scenario that retrieves content" />
      )}

      {orphans.length > 0 && (
        <>
          <p className="eyebrow">{"// other_guard_actions"}</p>
          <OrphanThreatTable threats={orphans} caption="threats without source provenance link" />
        </>
      )}
      {sessionId && (
        <div className="control-bar">
          <a
            className="btn ghost"
            href={`#case_files?agent=${encodeURIComponent(agentId)}&version=${encodeURIComponent(versionId)}&model=${encodeURIComponent(model)}&session=${encodeURIComponent(sessionId)}`}
          >
            case_files →
          </a>
          <a
            className="btn ghost"
            href={`#sources_trust?agent=${encodeURIComponent(agentId)}`}
          >
            sources_trust →
          </a>
        </div>
      )}
    </>
  );
}

function CascadeControlBar(props: {
  agentId: string;
  versionId: string;
  model: string;
  sessionId: string;
  lane: "versioned" | "unversioned";
  versions: AgentVersionRow[] | null;
  models: AgentModelRow[];
  sessions: SessionRow[] | null;
  sessionsTotal: number;
  agentOptions: FleetRow[];
  prefer: MutableRefObject<{ version?: string; model?: string; session?: string }>;
  setCascade: Dispatch<SetStateAction<CascadeState>>;
}) {
  const {
    agentId,
    versionId,
    model,
    sessionId,
    lane,
    versions,
    models,
    sessions,
    sessionsTotal,
    agentOptions,
    prefer,
    setCascade,
  } = props;

  return (
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
                  model: models.some((m) => m.model === s.model)
                    ? s.model
                    : (models[0]?.model ?? s.model),
                }),
              );
              return;
            }
            const row = (versions ?? []).find((x) => x.version_id === v);
            setCascade((s) =>
              cascadeReducer(s, {
                type: "set_version",
                versionId: v,
                model: row?.model ?? "",
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
      {sessions && sessions.length > 0 && (
        <span className="dim" role="status">
          {showingOfTotal(sessions.length, sessionsTotal || sessions.length)}
          {lane === "versioned" && versionId ? " · filter=agent_version" : ""}
        </span>
      )}
    </div>
  );
}

function InspectorSummary({
  summary,
  sessionId,
}: {
  summary: ReturnType<typeof ingestSummary>;
  sessionId: string;
}) {
  const block = summary.downstreamBlock;
  return (
    <div className="verdict">
      <div className="stat-row">
        <span>session</span>
        <span>
          <code>{sessionId}</code>
        </span>
      </div>
      <div className="stat-row">
        <span>sources</span>
        <span>{summary.sourceCount}</span>
      </div>
      <div className="stat-row">
        <span>threats</span>
        <span>{summary.threatCount}</span>
      </div>
      <div className="stat-row">
        <span>ingest</span>
        <span>
          <span className={`badge ${summary.ingestClean ? "ok" : "warn"}`}>
            [{summary.ingestClean ? "CLEAN" : "FLAGGED"}]
          </span>
        </span>
      </div>
      <div className="stat-row">
        <span>story</span>
        <span className="wrap">{summary.narrative}</span>
      </div>
      {block && (
        <div className="stat-row">
          <span>downstream</span>
          <span>
            <span className={`badge ${ACTION_CLASS[block.action ?? ""] ?? "warn"}`}>
              [{(block.action ?? "n/a").toUpperCase()}]
            </span>{" "}
            {block.checkpoint} · {block.category}/{block.subcategory} · risk{" "}
            {block.risk_score ?? "—"}
          </span>
        </div>
      )}
    </div>
  );
}

function IngestTimelineView({ timeline }: { timeline: ReturnType<typeof buildIngestTimeline> }) {
  return (
    <div className="history">
      {timeline.map((step) => {
        const s = step.source;
        const scan = s.scan_action ?? "n/a";
        return (
          <div key={s.source_id} className="history-row">
            <div className="stat-row">
              <span>
                step {step.index} · {ts(s.created_at)}
              </span>
              <span>
                <span className={`badge ${ACTION_CLASS[scan] ?? "ok"}`}>
                  [{scan.toUpperCase()}]
                </span>
              </span>
            </div>
            <p className="step">
              <code>{s.source_id}</code> · origin=<span className="wrap">{s.origin ?? "—"}</span> ·
              trust={s.trust_level ?? "—"} · findings={s.findings}
            </p>
            {step.linkedThreats.length > 0 && (
              <div className="col exploited" style={{ marginTop: 8 }}>
                <h3>provenance → threat</h3>
                {step.linkedThreats.map((t) => (
                  <ThreatLine key={t.threat_id} threat={t} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ThreatLine({ threat }: { threat: AgentThreatRow }) {
  return (
    <p className="step evidence">
      <code>{threat.threat_id}</code> · {threat.checkpoint} ·{" "}
      <span className={`badge ${ACTION_CLASS[threat.action ?? ""] ?? "warn"}`}>
        [{(threat.action ?? "n/a").toUpperCase()}]
      </span>{" "}
      · {threat.category}/{threat.subcategory} · risk {threat.risk_score ?? "—"}
      {threat.evidence_excerpt ? ` — ${threat.evidence_excerpt}` : ""}
    </p>
  );
}

function OrphanThreatTable({
  threats,
  caption,
}: {
  threats: AgentThreatRow[];
  caption: string;
}) {
  return (
    <table className="data-table">
      <caption className="dim">{caption}</caption>
      <thead>
        <tr>
          <th>time</th>
          <th>checkpoint</th>
          <th>action</th>
          <th>category</th>
          <th>risk</th>
          <th>evidence</th>
        </tr>
      </thead>
      <tbody>
        {threats.map((t) => (
          <tr key={t.threat_id}>
            <td className="dim">{ts(t.created_at ?? null)}</td>
            <td>{t.checkpoint ?? "—"}</td>
            <td>
              <span className={`badge ${ACTION_CLASS[t.action ?? ""] ?? "warn"}`}>
                [{(t.action ?? "n/a").toUpperCase()}]
              </span>
            </td>
            <td>
              {t.category}/{t.subcategory}
            </td>
            <td>{t.risk_score ?? "—"}</td>
            <td className="wrap">{t.evidence_excerpt ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
