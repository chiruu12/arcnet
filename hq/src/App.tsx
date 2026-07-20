import { useEffect, useState } from "react";

type FleetRow = {
  agent_id: string;
  name: string | null;
  exposure: string | null;
  health: {
    sessions_24h: number;
    threats_24h: number;
    blocked_24h: number;
    cost_24h_usd: number;
    active_signals: number;
  };
};

type SignozStatus = {
  signoz_url: string;
  ui_reachable: boolean;
  ui_status: number | string | null;
  api_key_present: boolean;
  query_range_ok: boolean | null;
  query_note: string;
};

const API = import.meta.env.VITE_ARCNET_API ?? "http://127.0.0.1:8000";

export function App() {
  const [fleet, setFleet] = useState<FleetRow[] | null>(null);
  const [signoz, setSignoz] = useState<SignozStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [f, s] = await Promise.all([
          fetch(`${API}/api/fleet`).then((r) => {
            if (!r.ok) throw new Error(`fleet ${r.status}`);
            return r.json();
          }),
          fetch(`${API}/api/signoz/status`).then((r) => {
            if (!r.ok) throw new Error(`signoz ${r.status}`);
            return r.json();
          }),
        ]);
        if (!cancelled) {
          setFleet(f);
          setSignoz(s);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) setErr(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main
      style={{
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        padding: 24,
        background: "#000",
        color: "#00e8ff",
        minHeight: "100vh",
      }}
    >
      <h1 style={{ margin: 0 }}>{"> arcnet"}</h1>
      <p style={{ color: "#8a9ba8" }}>phase 2 seam check — hq → server → signoz</p>
      {err && <pre style={{ color: "#ff6b6b" }}>error: {err}</pre>}
      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 14, color: "#8a9ba8" }}>signoz_status()</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{signoz ? JSON.stringify(signoz, null, 2) : "loading…"}</pre>
      </section>
      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 14, color: "#8a9ba8" }}>fleet()</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{fleet ? JSON.stringify(fleet, null, 2) : "loading…"}</pre>
      </section>
    </main>
  );
}
