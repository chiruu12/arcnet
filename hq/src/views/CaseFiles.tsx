import { useEffect, useState } from "react";
import { api } from "../api";
import { AgentJson, Empty, Seam, ts } from "../components";
import type { AgentEnvelope, Mode, SessionRow } from "../types";

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

export function CaseFiles({ mode }: { mode: Mode }) {
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [envelope, setEnvelope] = useState<AgentEnvelope | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .sessions()
      .then((s) => {
        if (cancelled) return;
        setSessions(s);
        if (s.length > 0) setSelected((cur) => cur || s[0].session_id);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
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

  if (mode === "agent") {
    if (selected) return <AgentJson view="incident" id={selected} />;
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>case_files</h1>
        <Empty hint="no session selected" />
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
        incident bundle for a coding agent: root cause · timeline · recommended actions ·
        fix-prompt preamble with SigNoz MCP hints. export → hand_to(claude_code).
      </p>
      {err && <Seam error={err} />}
      {sessions && sessions.length === 0 && (
        <Empty hint="no recorded sessions — run scripts/record_scenario.py or run-demo.sh first" />
      )}

      {sessions && sessions.length > 0 && (
        <div className="control-bar">
          <label>
            session
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              {sessions.map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {s.session_id} · {s.scenario ?? "—"} · {s.status} · {ts(s.started_at)}
                </option>
              ))}
            </select>
          </label>
          <a className="btn" href={api.caseFileUrl(selected)} download>
            export_case_file()
          </a>
        </div>
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
            <p className="step dim">
              {envelope?.hints?.raw_evidence ?? ""}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
