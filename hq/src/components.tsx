import { useEffect, useState } from "react";
import { api, toUserError } from "./api";
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
      <p className="eyebrow">{"// agent_view"}</p>
      <h1>
        GET /api/agent-view/{view}/{id}
      </h1>
      {err && <ViewSeam error={err} onRetry={retry} />}
      {!err && !env && <p className="lede">loading…</p>}
      {env && <pre className="agent-json">{JSON.stringify(env, null, 2)}</pre>}
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
