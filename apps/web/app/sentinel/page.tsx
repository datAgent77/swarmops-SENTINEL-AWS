"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- types -----------------------------------------------------------------
type ProviderState = { status: string; detail: string; tools?: number };
type Status = {
  on_duty: boolean;
  location: string;
  status: string;
  providers: { ring: ProviderState; bedrock: ProviderState; swarmops: ProviderState; alexa_mcp: ProviderState };
};
type TimelineItem = { action: string; decision: string | null; reason: string | null; occurred_at: string };
type Demo = {
  incident_id: string;
  incident: { risk: { risk_level: string; risk_score: number } };
  explanation: { risk_level: string; risk_score: number };
  ring_events: { t: string; label: string; provider_event_type: string | null; signature_verified: boolean }[];
  centerpiece: { ai_recommendation: string; decision: string; reason_codes: string[] };
  second_action: { ai_recommendation: string; decision: string; approval_id: string | null; action_request_id: string };
  timeline: TimelineItem[];
};

async function call(path: string, body?: unknown): Promise<{ ok: boolean; data: unknown }> {
  const res = await fetch(`${API_URL}${path}`, {
    method: body !== undefined ? "POST" : "GET",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return { ok: res.ok, data: await res.json().catch(() => ({})) };
}

// ---- colour tokens ---------------------------------------------------------
const C = {
  bg: "#0a1120", panel: "#111a2e", edge: "#1e2a44", text: "#e6ecf7", dim: "#8ea0c0",
  teal: "#2dd4bf", green: "#34d399", amber: "#fbbf24", red: "#f87171", blue: "#60a5fa",
};

const REASON_LABEL: Record<string, string> = {
  OUTSIDE_BUSINESS_HOURS: "Outside business hours",
  NO_VERIFIED_VISITOR: "No verified visitor",
  NO_APPROVED_ACCESS_REQUEST: "No approved access request",
  NO_VALID_CREDENTIAL: "No valid credential",
  RISK_TOO_HIGH: "Risk too high",
};

const TL_LABEL: Record<string, (t: TimelineItem) => string> = {
  incident_created: () => "Incident opened from correlated entrance events",
  observation_generated: () => "AI observation generated",
  risk_calculated: (t) => `Risk assessed ${t.decision ?? "HIGH"}`,
  policy_evaluated: () => "Security policy evaluated",
  action_proposed: (t) => (t.reason === "GRANT_TEMPORARY_ACCESS" ? "Temporary access proposed" : "Warning proposed"),
  action_denied: () => "ACCESS DENIED BY SECURITY POLICY",
  approval_requested: () => "Human approval required for warning",
  approval_granted: () => "Warning approved by security officer",
  execution_started: () => "Warning execution started",
  execution_completed: () => "Warning executed",
  duplicate_execution_prevented: () => "Duplicate blocked — executed exactly once",
};

function providerColor(status: string): string {
  if (["CONNECTED", "ACTIVE", "READY"].includes(status)) return C.green;
  if (status === "DEMO_MODE") return C.amber;
  if (status === "ERROR") return C.red;
  return C.dim;
}

export default function SentinelPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [demo, setDemo] = useState<Demo | null>(null);
  const [approval, setApproval] = useState<"idle" | "pending" | "approved" | "rejected">("idle");
  const [duplicate, setDuplicate] = useState<boolean | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("Press START DEMO to begin the guarded entrance scenario.");

  const loadStatus = useCallback(async () => {
    const { ok, data } = await call("/api/sentinel/status");
    if (ok) setStatus(data as Status);
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const refreshTimeline = useCallback(async (incidentId: string) => {
    const { ok, data } = await call(`/api/sentinel/timeline?incident_id=${incidentId}`);
    if (ok) setTimeline((data as { timeline: TimelineItem[] }).timeline);
  }, []);

  const start = async () => {
    setBusy(true);
    setDuplicate(null);
    const { ok, data } = await call("/api/sentinel/demo/start", {});
    if (ok) {
      const d = data as Demo;
      setDemo(d);
      setTimeline(d.timeline);
      setApproval("pending");
      setNote("Access was DENIED automatically. A warning needs your approval.");
    } else {
      setNote("Backend unavailable — start the API to run the demo.");
    }
    setBusy(false);
  };

  const reset = async () => {
    setBusy(true);
    await call("/api/sentinel/demo/reset", {});
    setDemo(null);
    setTimeline([]);
    setApproval("idle");
    setDuplicate(null);
    setNote("Demo reset. Press START DEMO to begin again.");
    await loadStatus();
    setBusy(false);
  };

  const decide = async (kind: "approve" | "reject") => {
    if (!demo?.second_action.approval_id) return;
    setBusy(true);
    const { ok, data } = await call(`/api/sentinel/${kind}`, {
      incident_id: demo.incident_id,
      approval_id: demo.second_action.approval_id,
      actor_id: "officer-sam",
    });
    if (ok) {
      setApproval(kind === "approve" ? "approved" : "rejected");
      setNote(kind === "approve" ? "Warning executed exactly once. Try replaying the same request." : "Warning rejected. No action taken.");
    } else {
      setNote(`Blocked by SwarmOps: ${(data as { error?: { code?: string } })?.error?.code ?? "denied"}`);
    }
    await refreshTimeline(demo.incident_id);
    setBusy(false);
  };

  const replay = async () => {
    if (!demo) return;
    setBusy(true);
    const { ok, data } = await call("/api/sentinel/propose", {
      incident_id: demo.incident_id,
      action_type: "SEND_WARNING",
      actor_id: "owner-alex",
      action_request_id: demo.second_action.action_request_id,
    });
    if (ok) {
      setDuplicate((data as { duplicate_prevented: boolean }).duplicate_prevented);
      setNote("Replayed the exact same request — duplicate execution prevented.");
    }
    await refreshTimeline(demo.incident_id);
    setBusy(false);
  };

  const pipelineStage = !demo ? 0 : approval === "approved" ? 5 : 3; // RING/BEDROCK/SWARMOPS done at start

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "system-ui, sans-serif" }}>
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "28px 20px 60px" }}>
        {/* Header */}
        <header style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 12, letterSpacing: 3, color: C.teal }}>SENTINEL</div>
            <h1 style={{ margin: "2px 0 0", fontSize: 26, fontWeight: 700 }}>AI Security Officer</h1>
            <div style={{ color: C.dim, fontSize: 13, marginTop: 4 }}>
              {status?.location ?? "SaitALCorp Office"} · {status?.status ?? "ENTRANCE MONITORED"}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 14px",
              borderRadius: 999, border: `1px solid ${C.green}`, background: "rgba(52,211,153,0.12)", fontWeight: 700 }}>
              <span style={{ width: 9, height: 9, borderRadius: "50%", background: C.green,
                boxShadow: `0 0 10px ${C.green}` }} />
              ON DUTY
            </span>
          </div>
        </header>

        {/* Provider indicators */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10, marginTop: 18 }}>
          {status &&
            (["ring", "bedrock", "swarmops", "alexa_mcp"] as const).map((k) => {
              const p = status.providers[k];
              const name = { ring: "RING", bedrock: "BEDROCK", swarmops: "SWARMOPS", alexa_mcp: "ALEXA+ MCP" }[k];
              return (
                <div key={k} style={{ background: C.panel, border: `1px solid ${C.edge}`, borderRadius: 10, padding: "12px 14px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 12, letterSpacing: 1.5, color: C.dim }}>{name}</span>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: providerColor(p.status) }} />
                  </div>
                  <div style={{ fontWeight: 700, marginTop: 6, color: providerColor(p.status) }}>{p.status}</div>
                  <div style={{ fontSize: 11, color: C.dim, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.detail}</div>
                </div>
              );
            })}
        </div>

        {/* Guided demo controls */}
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 20, flexWrap: "wrap" }}>
          <button onClick={start} disabled={busy} style={primaryBtn(C.teal, busy)}>START DEMO</button>
          <button onClick={reset} disabled={busy} style={ghostBtn(busy)}>RESET DEMO</button>
          <span style={{ color: C.dim, fontSize: 13 }}>{note}</span>
        </div>

        {/* Pipeline */}
        <Pipeline stage={pipelineStage} />

        {demo && (
          <>
            {/* Incident card */}
            <section style={card()}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
                <div style={{ fontSize: 13, letterSpacing: 1.5, color: C.red, fontWeight: 700 }}>HIGH-RISK ENTRANCE ACTIVITY</div>
                <div style={{ fontSize: 22, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>23:42</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, marginTop: 12 }}>
                <Fact k="BUILDING" v="CLOSED" tone={C.red} />
                <Fact k="EXPECTED VISITOR" v="NONE" tone={C.red} />
                <Fact k="ACCESS REQUEST" v="NONE" tone={C.red} />
                <Fact k="CREDENTIAL" v="NONE" tone={C.red} />
              </div>
            </section>

            {/* CENTERPIECE: AI recommends grant → DENIED */}
            <section style={{ ...card(), borderColor: C.red, background: "rgba(248,113,113,0.06)" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 16, alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.blue }}>AI RECOMMENDATION</div>
                  <div style={{ fontSize: 20, fontWeight: 800, marginTop: 6 }}>GRANT TEMPORARY ACCESS</div>
                  <div style={{ fontSize: 12, color: C.dim, marginTop: 4 }}>probabilistic · advisory only</div>
                </div>
                <div style={{ fontSize: 26, color: C.dim }}>→</div>
                <div>
                  <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.dim }}>SWARMOPS POLICY</div>
                  <div style={{ fontSize: 30, fontWeight: 900, color: C.red, marginTop: 2 }}>DENIED</div>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 18, color: C.text, fontSize: 13 }}>
                    {demo.centerpiece.reason_codes.map((c) => (
                      <li key={c}>{REASON_LABEL[c] ?? c}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div style={{ fontSize: 11, color: C.dim, marginTop: 12, textAlign: "center" }}>
                Deterministic decision — the AI cannot override it.
              </div>
            </section>

            {/* SECOND ACTION: send warning → human approval */}
            <section style={card()}>
              <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.blue }}>AI RECOMMENDATION</div>
                  <div style={{ fontSize: 18, fontWeight: 800, marginTop: 4 }}>SEND WARNING</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.dim }}>SWARMOPS</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: C.amber }}>HUMAN APPROVAL REQUIRED</div>
                </div>
              </div>

              <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                {approval === "pending" && (
                  <>
                    <span style={{ color: C.dim, fontSize: 13 }}>Review action (as security officer):</span>
                    <button onClick={() => decide("approve")} disabled={busy} style={primaryBtn(C.green, busy)}>APPROVE</button>
                    <button onClick={() => decide("reject")} disabled={busy} style={dangerBtn(busy)}>REJECT</button>
                  </>
                )}
                {approval === "approved" && (
                  <>
                    <span style={{ padding: "6px 14px", borderRadius: 8, background: "rgba(52,211,153,0.15)", border: `1px solid ${C.green}`, color: C.green, fontWeight: 800 }}>
                      ACTION EXECUTED
                    </span>
                    <button onClick={replay} disabled={busy} style={ghostBtn(busy)}>Replay the exact same request</button>
                    {duplicate === true && (
                      <span style={{ padding: "6px 14px", borderRadius: 8, background: "rgba(251,191,36,0.15)", border: `1px solid ${C.amber}`, color: C.amber, fontWeight: 800 }}>
                        DUPLICATE BLOCKED · EXECUTED EXACTLY ONCE
                      </span>
                    )}
                  </>
                )}
                {approval === "rejected" && (
                  <span style={{ color: C.red, fontWeight: 700 }}>Warning rejected — no action taken.</span>
                )}
              </div>
            </section>

            {/* Timeline */}
            <section style={card()}>
              <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.dim, marginBottom: 10 }}>INCIDENT TIMELINE</div>
              <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {demo.ring_events.map((e, i) => (
                  <TL key={`r${i}`} t={e.t} label={e.label} tone={C.blue} />
                ))}
                {timeline
                  .filter((t) => t.action in TL_LABEL)
                  .map((t, i) => (
                    <TL
                      key={`t${i}`}
                      t="23:47"
                      label={TL_LABEL[t.action](t)}
                      tone={t.action === "action_denied" ? C.red : t.action === "duplicate_execution_prevented" ? C.amber : C.teal}
                    />
                  ))}
              </ol>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

// ---- small components ------------------------------------------------------
function Fact({ k, v, tone }: { k: string; v: string; tone: string }) {
  return (
    <div style={{ background: "#0d1526", border: `1px solid ${C.edge}`, borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ fontSize: 11, letterSpacing: 1, color: C.dim }}>{k}</div>
      <div style={{ fontWeight: 800, color: tone, marginTop: 4 }}>{v}</div>
    </div>
  );
}

function TL({ t, label, tone }: { t: string; label: string; tone: string }) {
  return (
    <li style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "6px 0" }}>
      <span style={{ fontVariantNumeric: "tabular-nums", color: C.dim, minWidth: 44, fontSize: 13 }}>{t}</span>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: tone, marginTop: 6, flexShrink: 0 }} />
      <span style={{ fontSize: 14 }}>{label}</span>
    </li>
  );
}

const STAGES = [
  { top: "RING", bot: "OBSERVE" },
  { top: "BEDROCK", bot: "UNDERSTAND" },
  { top: "SWARMOPS", bot: "ASSESS + AUTHORIZE" },
  { top: "HUMAN", bot: "APPROVE WHEN REQUIRED" },
  { top: "ACTION", bot: "EXECUTE" },
];

function Pipeline({ stage }: { stage: number }) {
  return (
    <div style={{ display: "flex", alignItems: "stretch", gap: 8, marginTop: 20, overflowX: "auto" }}>
      {STAGES.map((s, i) => {
        const active = i < stage;
        return (
          <div key={s.top} style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 150 }}>
            <div style={{ flex: 1, textAlign: "center", padding: "12px 8px", borderRadius: 10,
              border: `1px solid ${active ? C.teal : C.edge}`,
              background: active ? "rgba(45,212,191,0.10)" : C.panel }}>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: 1, color: active ? C.teal : C.text }}>{s.top}</div>
              <div style={{ fontSize: 10, color: C.dim, marginTop: 3 }}>{s.bot}</div>
            </div>
            {i < STAGES.length - 1 && <span style={{ color: C.dim }}>→</span>}
          </div>
        );
      })}
    </div>
  );
}

// ---- button styles ---------------------------------------------------------
function primaryBtn(color: string, busy: boolean): React.CSSProperties {
  return { padding: "9px 18px", borderRadius: 8, border: `1px solid ${color}`,
    background: busy ? "rgba(255,255,255,0.08)" : color, color: busy ? C.dim : "#04121a",
    fontWeight: 800, letterSpacing: 0.5, cursor: busy ? "default" : "pointer" };
}
function dangerBtn(busy: boolean): React.CSSProperties {
  return { padding: "9px 18px", borderRadius: 8, border: `1px solid ${C.red}`,
    background: "transparent", color: C.red, fontWeight: 800, cursor: busy ? "default" : "pointer" };
}
function ghostBtn(busy: boolean): React.CSSProperties {
  return { padding: "9px 16px", borderRadius: 8, border: `1px solid ${C.edge}`,
    background: "transparent", color: C.text, cursor: busy ? "default" : "pointer" };
}
function card(): React.CSSProperties {
  return { background: C.panel, border: `1px solid ${C.edge}`, borderRadius: 14, padding: 18, marginTop: 16 };
}
