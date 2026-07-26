import { useEffect, useState } from "react";
import { api, toUserError } from "./api";
import { envelopeToToon, encodeToon } from "./toon";
import type { AgentEnvelope } from "./types";
import { useRetryToken } from "./viewRetry";

export function Seam({ error }: { error: string }) {
  return <p className="err">seam: {error}</p>;
}

/** Error seam with an explicit retry affordance for failed view fetches. */
export function ViewSeam({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="view-seam">
      <Seam error={error} />
      <button type="button" className="btn ghost" onClick={onRetry}>
        retry()
      </button>
    </div>
  );
}

export function Empty({ hint }: { hint: string }) {
  return (
    <div className="empty">
      <p className="empty-title">no_data()</p>
      <p className="empty-hint">{hint}</p>
    </div>
  );
}

/** Terminal chrome for TOON agent_view panels. */
export function ToonPanel({ title, body }: { title: string; body: string }) {
  return (
    <div className="toon-panel">
      <div className="toon-chrome">
        <span className="toon-dot red" />
        <span className="toon-dot amber" />
        <span className="toon-dot green" />
        <span className="toon-title">{title}</span>
      </div>
      <pre className="agent-json toon-body">{body}</pre>
    </div>
  );
}

/** Renders arbitrary JSON-ish data as TOON (agent_view helper). */
export function AgentToonBody({
  title,
  value,
}: {
  title: string;
  value: unknown;
}) {
  const body = typeof value === "string" ? value : encodeToon(value);
  return <ToonPanel title={title} body={body} />;
}

/** Renders the machine-optimal twin of a view: GET /api/agent-view/{view}/{id}. */
export function AgentJson({ view, id }: { view: string; id: string }) {
  const [env, setEnv] = useState<AgentEnvelope | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [retryAt, retry] = useRetryToken();

  useEffect(() => {
    let cancelled = false;
    setEnv(null);
    setErr(null);
    api
      .agentView(view, id)
      .then((e) => {
        if (!cancelled) setEnv(e);
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(toUserError(e));
      });
    return () => {
      cancelled = true;
    };
  }, [view, id, retryAt]);

  return (
    <>
      <p className="eyebrow">{"// agent_view · toon"}</p>
      <h1>
        GET /api/agent-view/{view}/{id}
      </h1>
      {err && <ViewSeam error={err} onRetry={retry} />}
      {!err && !env && <p className="lede">loading…</p>}
      {env && <ToonPanel title={`${view}.toon`} body={envelopeToToon(env)} />}
    </>
  );
}

export function ts(ms: number | null | undefined): string {
  if (!ms) return "—";
  return new Date(ms).toISOString().replace("T", " ").slice(0, 19);
}

export function money(v: unknown): string {
  const n = Number(v);
  return Number.isFinite(n) ? `$${n.toFixed(4)}` : "—";
}
