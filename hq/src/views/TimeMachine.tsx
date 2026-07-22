import { useEffect, useMemo, useRef, useState } from "react";
import { api, subscribeBus, type AgentVersionRow, type ReplayRow } from "../api";
import {
  cascadeReducer,
  emptyCascade,
  preferHeroSession,
  preferVersion,
  type CascadeState,
} from "../cascade";
import { AgentJson, Empty, Seam, money, ts } from "../components";
import type { AgentModelRow, CascadeLink, FleetRow, Mode, SessionRow, Verdict } from "../types";

type Progress = { step: number; total_steps: number; phase: string } | null;

const HERO_SESSIONS = ["s_2af44726", "s_ecfdb55d"];
const DEFAULT_CANDIDATE = "gpt-4o";

function badgeFor(run: Record<string, unknown>, isBaseline: boolean): { label: string; cls: string } {
  if ("resisted_injection" in run) {
    return run.resisted_injection
      ? { label: "[RESISTED]", cls: "ok" }
      : { label: "[EXPLOITED]", cls: "danger" };
  }
  const goal = String(run.goal_reached ?? "");
  if (goal === "killed") return { label: "[KILLED]", cls: "danger" };
  if (goal === "failed") return { label: "[FAILED]", cls: "danger" };
  if (goal === "clean") return { label: "[OK]", cls: "ok" };
  return isBaseline ? { label: `[${goal.toUpperCase()}]`, cls: "warn" } : { label: "[STOPPED]", cls: "ok" };
}

const DIMENSIONS: [string, (v: unknown) => string][] = [
  ["goal_reached", String],
  ["steps", String],
  ["tool_errors", String],
  ["cost_usd", money],
  ["latency_ms", String],
  ["tokens", String],
  ["resisted_injection", String],
  ["exfil_attempts", String],
];

export function TimeMachine({
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
  const [candidate, setCandidate] = useState(DEFAULT_CANDIDATE);
  const [replays, setReplays] = useState<ReplayRow[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<Progress>(null);
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
    const unsubscribe = subscribeBus((ev) => {
      if (ev.event !== "replay_progress" || cancelled) return;
      const d = ev.data as { step?: number; total_steps?: number; phase?: string };
      setProgress({ step: d.step ?? 0, total_steps: d.total_steps ?? 0, phase: d.phase ?? "" });
    });
    return () => {
      cancelled = true;
      unsubscribe();
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
      .then(async (all) => {
        if (cancelled) return;
        let rows = all;
        let noPins = false;
        if (rows.length === 0 && params.agent_version) {
          rows = await api.sessions({ agent_id: agentId, model });
          noPins = true;
        }
        if (cancelled) return;
        const replayable = rows.filter((s) => s.has_transcript);
        setVersionHasNoPins(noPins);
        setSessions(replayable);
        const want = prefer.current.session;
        prefer.current.session = undefined;
        const next = preferHeroSession(
          replayable.map((r) => r.session_id),
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
      setReplays([]);
      setVerdict(null);
      return;
    }
    let cancelled = false;
    api
      .replays(sessionId)
      .then((r) => {
        if (cancelled) return;
        setReplays(r);
        setVerdict(r.length > 0 ? r[0].verdict : null);
      })
      .catch(() => {
        if (!cancelled) setReplays([]);
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

  const session = useMemo(
    () => sessions?.find((s) => s.session_id === sessionId) ?? null,
    [sessions, sessionId],
  );

  async function run() {
    if (!sessionId || running) return;
    setRunning(true);
    setErr(null);
    setProgress(null);
    try {
      const v = await api.runReplay(sessionId, candidate.trim());
      setVerdict(v);
      const r = await api.replays(sessionId);
      setReplays(r);
    } catch (e: unknown) {
      setErr(String(e));
    } finally {
      setRunning(false);
      setProgress(null);
    }
  }

  if (mode === "agent") {
    if (verdict?.replay_id) return <AgentJson view="replay" id={verdict.replay_id} />;
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>time_machine</h1>
        <Empty hint="no replay selected — run replay.run() in human_view first" />
      </>
    );
  }

  const b = (verdict?.baseline ?? {}) as Record<string, unknown>;
  const c = (verdict?.candidate ?? {}) as Record<string, unknown>;
  const isThreat = verdict != null && "resisted_injection" in c;

  return (
    <>
      <p className="eyebrow">{"// counterfactual_replay"}</p>
      <h1>
        {isThreat
          ? "would a different model have resisted the attack?"
          : "would a different model have handled this incident better?"}
      </h1>
      <p className="lede">
        replay one recorded session against a candidate · tool_outputs=mocked · guard=identical ·
        3 runs, majority verdict. pick agent → version → model → session.
      </p>
      {err && <Seam error={err} />}

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
            {(fleet ?? []).map((a) => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.agent_id}
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
                {v.version} · {v.model ?? "—"}
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
            {models.length === 0 && !model && <option value="">no sessions</option>}
            {model && !models.some((m) => m.model === model) && (
              <option value={model}>{model} · from version</option>
            )}
            {models.map((m) => (
              <option key={m.model} value={m.model}>
                {m.model} · {m.session_count}
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
            {(sessions ?? []).map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id} · {s.scenario ?? "—"} · {s.status}
              </option>
            ))}
          </select>
        </label>
        <label>
          candidate_model
          <input value={candidate} onChange={(e) => setCandidate(e.target.value)} />
        </label>
        <button className="btn" type="button" disabled={running || !sessionId} onClick={run}>
          {running
            ? progress
              ? `replay.run() ${progress.phase} ${progress.step}/${progress.total_steps}`
              : "replay.run() …"
            : "replay.run()"}
        </button>
      </div>

      {lane === "unversioned" && (
        <p className="dim">
          lane=unversioned — filtering by observed model only (no version pin).
        </p>
      )}
      {versionHasNoPins && lane === "versioned" && (
        <p className="dim">
          no sessions pinned to this version yet — showing unpinned replayable sessions for model=
          {model}.
        </p>
      )}

      {sessions && sessions.length === 0 && (
        <Empty hint="no replayable sessions for this agent + version/model — pick another, or record a session with a transcript" />
      )}

      {session && (
        <p className="meta">
          baseline [{session.model ?? "?"} · recorded {ts(session.started_at)}] ⇄ candidate [
          {candidate} · replay] · scenario={session.scenario ?? "—"} · goal="{session.goal ?? "—"}"
        </p>
      )}

      {verdict && (
        <>
          <div className="diff">
            {[
              { run: b, isBaseline: true, title: `${String(b.model ?? "baseline")} (recorded)` },
              { run: c, isBaseline: false, title: `${String(c.model ?? "candidate")} (replay)` },
            ].map(({ run: r, isBaseline, title }) => {
              const badge = badgeFor(r, isBaseline);
              return (
                <div
                  key={title}
                  className={`col ${badge.cls === "danger" ? "exploited" : badge.cls === "ok" ? "resisted" : ""}`}
                >
                  <h3>
                    {title} <span className={`badge ${badge.cls}`}>{badge.label}</span>
                  </h3>
                  {DIMENSIONS.filter(([k]) => k in r).map(([k, fmt]) => (
                    <div className="stat-row" key={k}>
                      <span>{k}</span>
                      <span>{fmt(r[k])}</span>
                    </div>
                  ))}
                  {!isBaseline && (verdict.divergences ?? []).length > 0 && (
                    <div className="divergences">
                      {"// divergences"}
                      {verdict.divergences.map((d, i) => (
                        <p className="step" key={i}>
                          step {d.step}: {d.note}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="verdict">
            <div className="traffic">
              <i className="r" />
              <i className="y" />
              <i className="g" />
            </div>
            <div className="meta">
              replay.diff · {verdict.replay_id} · confidence={verdict.confidence}
            </div>
            <table>
              <tbody>
                {DIMENSIONS.filter(([k]) => k in b || k in c).map(([k, fmt]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>
                      {k in b ? fmt(b[k]) : "—"} → {k in c ? fmt(c[k]) : "—"}
                    </td>
                  </tr>
                ))}
                <tr>
                  <td>verdict</td>
                  <td>
                    <span
                      className={`badge ${
                        verdict.verdict === "improved"
                          ? "ok"
                          : verdict.verdict === "regressed"
                            ? "danger"
                            : "warn"
                      }`}
                    >
                      [{verdict.verdict.toUpperCase()}]
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div className="rec">{verdict.recommendation}</div>
            <div className="actions">
              <a className="btn" href={api.caseFileUrl(verdict.session_id)} download>
                hand_to(claude_code)
              </a>
              <span className="dim sp-l">exports the case file bundle (md + json)</span>
            </div>
          </div>
        </>
      )}

      {!verdict && sessionId && (
        <Empty hint={`no replay for ${sessionId} yet — hit replay.run() to compare models`} />
      )}

      {replays.length > 1 && (
        <div className="history">
          <p className="eyebrow">{"// replay_history"}</p>
          {replays.map((r) => (
            <button
              key={r.replay_id}
              type="button"
              className={`history-row ${verdict?.replay_id === r.replay_id ? "active" : ""}`}
              onClick={() => setVerdict(r.verdict)}
            >
              {r.replay_id} · {r.candidate_model ?? r.candidate_prompt_ref ?? "?"} ·{" "}
              {r.verdict?.verdict ?? "?"} · {ts(r.created_at)}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
