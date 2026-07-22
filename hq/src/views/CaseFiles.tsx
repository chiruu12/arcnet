import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
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

function preferHero(sessions: SessionRow[], prefer?: string): string {
  if (prefer && sessions.some((s) => s.session_id === prefer)) return prefer;
  for (const id of HERO_SESSIONS) {
    if (sessions.some((s) => s.session_id === id)) return id;
  }
  return sessions[0]?.session_id ?? "";
}

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
  const [agentId, setAgentId] = useState(deepLink?.agent ?? "");
  const [models, setModels] = useState<AgentModelRow[]>([]);
  const [model, setModel] = useState(deepLink?.model ?? "");
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);
  const [selected, setSelected] = useState(deepLink?.session ?? "");
  const [envelope, setEnvelope] = useState<AgentEnvelope | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const preferSession = useRef(deepLink?.session);
  const preferModel = useRef(deepLink?.model);

  useEffect(() => {
    if (!deepLink?.agent || deepLink.agent === agentId) return;
    preferSession.current = deepLink.session;
    preferModel.current = deepLink.model;
    setAgentId(deepLink.agent);
  }, [deepLink?.agent, deepLink?.session, deepLink?.model, agentId]);

  useEffect(() => {
    let cancelled = false;
    api
      .fleet()
      .then((f) => {
        if (cancelled) return;
        setFleet(f);
        if (f.length === 0) return;
        setAgentId((cur) => {
          if (cur && f.some((a) => a.agent_id === cur)) return cur;
          if (deepLink?.agent && f.some((a) => a.agent_id === deepLink.agent)) {
            return deepLink.agent;
          }
          return f[0].agent_id;
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
      setModels([]);
      setModel("");
      return;
    }
    let cancelled = false;
    setSelected("");
    setSessions(null);
    api
      .agentModels(agentId)
      .then((rows) => {
        if (cancelled) return;
        setModels(rows);
        const want = preferModel.current;
        preferModel.current = undefined;
        const next =
          want && rows.some((r) => r.model === want) ? want : (rows[0]?.model ?? "");
        setModel(next);
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
      setSelected("");
      return;
    }
    let cancelled = false;
    api
      .sessions({ agent_id: agentId, model })
      .then((s) => {
        if (cancelled) return;
        setSessions(s);
        const want = preferSession.current;
        preferSession.current = undefined;
        setSelected(preferHero(s, want));
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, model]);

  useEffect(() => {
    if (!selected) {
      setEnvelope(null);
      return;
    }
    let cancelled = false;
    setEnvelope(null);
    api
      .agentView("incident", selected)
      .then((e) => {
        if (!cancelled) setEnvelope(e);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  useEffect(() => {
    if (!onDeepLinkChange || !agentId) return;
    const next = {
      agent: agentId,
      model: model || undefined,
      session: selected || undefined,
    };
    if (
      deepLink?.agent === next.agent &&
      deepLink?.model === next.model &&
      deepLink?.session === next.session
    ) {
      return;
    }
    onDeepLinkChange(next);
  }, [agentId, model, selected, onDeepLinkChange, deepLink?.agent, deepLink?.model, deepLink?.session]);

  const agentOptions = useMemo(() => fleet ?? [], [fleet]);

  if (mode === "agent") {
    if (selected) return <AgentJson view="incident" id={selected} />;
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>case_files</h1>
        <Empty hint="select agent → model → session in human_view, then toggle agent_view" />
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
        fix-prompt with SigNoz MCP hints. pick agent → model → session, then export.
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
                preferModel.current = undefined;
                preferSession.current = undefined;
                setAgentId(e.target.value);
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
            model
            <select
              value={model}
              onChange={(e) => {
                preferSession.current = undefined;
                setModel(e.target.value);
              }}
              disabled={models.length === 0}
            >
              {models.length === 0 && <option value="">no sessions for agent</option>}
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
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={!sessions || sessions.length === 0}
            >
              {sessions && sessions.length === 0 && <option value="">no sessions</option>}
              {(sessions ?? []).map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {s.session_id} · {s.scenario ?? "—"} · {s.status} · {ts(s.started_at)}
                </option>
              ))}
            </select>
          </label>
          {selected && (
            <a className="btn" href={api.caseFileUrl(selected)} download>
              export_case_file()
            </a>
          )}
        </div>
      )}

      {sessions && sessions.length === 0 && agentId && model && (
        <Empty hint="no sessions for this agent + model — pick another model or run a scenario" />
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
