import { useEffect, useMemo, useState } from "react";
import { api, subscribeBus, type ReplayRow } from "../api";
import { AgentJson, Empty, Seam, money, ts } from "../components";
import type { Mode, SessionRow, Verdict } from "../types";

type Progress = { step: number; total_steps: number; phase: string } | null;

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

export function TimeMachine({ mode }: { mode: Mode }) {
  const [sessions, setSessions] = useState<SessionRow[] | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [candidate, setCandidate] = useState("gpt-4o");
  const [replays, setReplays] = useState<ReplayRow[]>([]);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<Progress>(null);
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
    const unsubscribe = subscribeBus((ev) => {
      if (ev.event !== "replay_progress" || cancelled) return;
      const d = ev.data as { step?: number; total_steps?: number; phase?: string };
      setProgress({ step: d.step ?? 0, total_steps: d.total_steps ?? 0, phase: d.phase ?? "" });
    });
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    api
      .replays(selected)
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
  }, [selected]);

  const session = useMemo(
    () => sessions?.find((s) => s.session_id === selected) ?? null,
    [sessions, selected],
  );

  async function run() {
    if (!selected || running) return;
    setRunning(true);
    setErr(null);
    setProgress(null);
    try {
      const v = await api.runReplay(selected, candidate.trim());
      setVerdict(v);
      const r = await api.replays(selected);
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
        3 runs, majority verdict.
      </p>
      {err && <Seam error={err} />}

      <div className="control-bar">
        <label>
          session
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {(sessions ?? []).map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id} · {s.scenario ?? "—"} · {s.status} · {s.model ?? "—"}
              </option>
            ))}
          </select>
        </label>
        <label>
          candidate_model
          <input value={candidate} onChange={(e) => setCandidate(e.target.value)} />
        </label>
        <button className="btn" type="button" disabled={running || !selected} onClick={run}>
          {running
            ? progress
              ? `replay.run() ${progress.phase} ${progress.step}/${progress.total_steps}`
              : "replay.run() …"
            : "replay.run()"}
        </button>
      </div>

      {sessions && sessions.length === 0 && (
        <Empty hint="no recorded sessions — run scripts/record_scenario.py or run-demo.sh first" />
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

      {!verdict && selected && (
        <Empty hint={`no replay for ${selected} yet — hit replay.run() to compare models`} />
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
