"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RingInfo = { provider: string; status: string; detail: string };

// Honest color mapping: green ONLY when the backend reports a verified CONNECTED
// state. DEMO_MODE is amber, NOT_CONFIGURED grey, ERROR red.
const COLORS: Record<string, string> = {
  CONNECTED: "#16a34a",
  DEMO_MODE: "#d97706",
  NOT_CONFIGURED: "#6b7280",
  ERROR: "#dc2626",
};

const LABELS: Record<string, string> = {
  CONNECTED: "Connected",
  DEMO_MODE: "Demo mode",
  NOT_CONFIGURED: "Not configured",
  ERROR: "Error",
};

export function RingStatus() {
  const [info, setInfo] = useState<RingInfo | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`${API_URL}/api/ring/status`);
        if (!res.ok) throw new Error(String(res.status));
        const data = (await res.json()) as RingInfo;
        if (alive) setInfo(data);
      } catch {
        if (alive) setInfo({ provider: "ring", status: "ERROR", detail: "status unavailable" });
      }
    };
    load();
    const t = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const status = info?.status ?? "NOT_CONFIGURED";
  const color = COLORS[status] ?? COLORS.NOT_CONFIGURED;
  const label = LABELS[status] ?? status;

  return (
    <div className="chip ring" title={info?.detail ?? "Ring sensing layer status"}>
      <span className="chip-k">RING</span>
      <span
        aria-hidden
        style={{
          display: "inline-block",
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          marginRight: 6,
        }}
      />
      {label}
    </div>
  );
}
