import { useEffect, useRef, useState } from "react";
import { api, subscribeBus } from "../api";
import { Empty, Seam, ts } from "../components";
import { HITL_RELAY_HONESTY, hitlPayloadSummary } from "../hitlUtils";
import { showingOfTotal } from "../pageLabel";
import type { HitlRow, Mode } from "../types";

const HITL_PAGE = 40;

const STATUS_CLASS: Record<string, string> = {
  pending: "warn",
  approved: "ok",
  rejected: "danger",
  expired: "dim",
};

export function Hitl({ mode }: { mode: Mode }) {
  const [rows, setRows] = useState<HitlRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [liveCount, setLiveCount] = useState(0);
  const [deciding, setDeciding] = useState<string | null>(null);
  const seenIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    seenIdsRef.current = new Set();
    setRows(null);
    setTotal(0);
    setLiveCount(0);
    setErr(null);
    api
      .hitlPage({ limit: HITL_PAGE, offset: 0 })
      .then((page) => {
        if (!cancelled) {
          seenIdsRef.current = new Set(page.rows.map((r) => r.hitl_id).filter(Boolean));
          setRows(page.rows);
          setTotal(page.total);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(String(e));
      });
    const unsubscribe = subscribeBus((ev) => {
      if (cancelled || ev.event !== "hitl_request") return;
      const row = ev.data as unknown as HitlRow;
      if (!row.hitl_id) return;
      const isNew = !seenIdsRef.current.has(row.hitl_id);
      if (isNew) {
        seenIdsRef.current.add(row.hitl_id);
        setTotal((n) => n + 1);
        setLiveCount((n) => n + 1);
      }
      setRows((prev) => {
        const rest = (prev ?? []).filter((r) => r.hitl_id !== row.hitl_id);
        return [row, ...rest].slice(0, HITL_PAGE);
      });
    });
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  async function decide(hitlId: string, decision: "approved" | "rejected") {
    setDeciding(hitlId);
    setErr(null);
    try {
      const updated = await api.decideHitl(hitlId, decision);
      setRows((prev) => {
        const rest = (prev ?? []).filter((r) => r.hitl_id !== hitlId);
        return [updated, ...rest].slice(0, HITL_PAGE);
      });
    } catch (e: unknown) {
      setErr(String(e));
    } finally {
      setDeciding(null);
    }
  }

  if (mode === "agent") {
    return (
      <>
        <p className="eyebrow">{"// agent_view"}</p>
        <h1>hitl</h1>
        <p className="lede dim">{HITL_RELAY_HONESTY}</p>
        {err && <Seam error={err} />}
        {!err && !rows && <p className="lede">loading…</p>}
        {rows && <pre className="agent-json">{JSON.stringify(rows, null, 2)}</pre>}
      </>
    );
  }

  return (
    <>
      <p className="eyebrow">{"// observe"}</p>
      <h1>hitl</h1>
      <p className="lede">
        human-in-the-loop approvals · sse=/signals/stream (hitl_request)
        {liveCount > 0 && ` · ${liveCount} live event${liveCount === 1 ? "" : "s"} this session`}
      </p>
      <p className="dim honesty">{HITL_RELAY_HONESTY}</p>
      {err && <Seam error={err} />}
      {!err && !rows && <p className="lede">loading…</p>}
      {rows && rows.length === 0 && (
        <Empty hint="no HITL requests yet — pause signals from a guarded agent create rows via POST /api/hitl" />
      )}
      {rows && rows.length > 0 && (
        <>
          <p className="dim" role="status">
            {showingOfTotal(rows.length, total)}
            {total > rows.length ? ` · page size ${HITL_PAGE}` : ""}
          </p>
          <table className="data-table">
            <thead>
              <tr>
                <th>time</th>
                <th>hitl_id</th>
                <th>run_id</th>
                <th>session</th>
                <th>payload</th>
                <th>status</th>
                <th>decided</th>
                <th>actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.hitl_id}>
                  <td className="dim">{ts(r.created_at)}</td>
                  <td className="dim">
                    <code>{r.hitl_id}</code>
                  </td>
                  <td className="dim">
                    <code>{r.run_id}</code>
                  </td>
                  <td className="dim">
                    <code>{r.session_id ?? "—"}</code>
                  </td>
                  <td className="wrap">{hitlPayloadSummary(r.payload)}</td>
                  <td>
                    <span className={`badge ${STATUS_CLASS[r.status] ?? "ok"}`}>
                      [{r.status.toUpperCase()}]
                    </span>
                  </td>
                  <td className="dim">{ts(r.decided_at)}</td>
                  <td>
                    {r.status === "pending" ? (
                      <span className="inline-actions">
                        <button
                          type="button"
                          className="btn"
                          disabled={deciding === r.hitl_id}
                          onClick={() => decide(r.hitl_id, "approved")}
                        >
                          approve
                        </button>
                        <button
                          type="button"
                          className="btn ghost"
                          disabled={deciding === r.hitl_id}
                          onClick={() => decide(r.hitl_id, "rejected")}
                        >
                          reject
                        </button>
                      </span>
                    ) : (
                      <span className="dim">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
