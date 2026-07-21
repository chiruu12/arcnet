import { useEffect, useState } from "react";
import { api } from "./api";
import type { AgentEnvelope } from "./types";

export function Seam({ error }: { error: string }) {
  return <p className="err">seam: {error}</p>;
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
        if (!cancelled) setErr(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [view, id]);

  return (
    <>
      <p className="eyebrow">{"// agent_view"}</p>
      <h1>
        GET /api/agent-view/{view}/{id}
      </h1>
      {err && <Seam error={err} />}
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
