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
  bg: "#0a1120", panel: "#111a2e", edge: "#1e2a44", text: "#eef2fa", dim: "#a6b6d6",
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
  risk_calculated: (t) => `Risk assessed ${t.decision ?? "CRITICAL"}`,
  policy_evaluated: (t) => (t.reason === "GRANT_TEMPORARY_ACCESS" ? "Access policy evaluated" : "Warning policy evaluated"),
  action_proposed: (t) => (t.reason === "GRANT_TEMPORARY_ACCESS" ? "AI proposed temporary access" : "AI proposed to send a warning"),
  action_denied: () => "ACCESS DENIED BY SECURITY POLICY",
  approval_requested: () => "Human approval required for warning",
  approval_granted: () => "Human approval granted",
  execution_started: () => "Warning execution started",
  execution_completed: () => "Warning executed successfully",
  duplicate_execution_prevented: () => "Duplicate blocked — no second warning sent",
};

// Events after the human approval advance to 23:48 (deterministic scene timing).
const TL_LATE = new Set(["approval_granted", "execution_started", "execution_completed", "duplicate_execution_prevented"]);
const tlTime = (action: string): string => (TL_LATE.has(action) ? "23:48" : "23:47");

function providerColor(status: string): string {
  if (["CONNECTED", "ACTIVE", "READY"].includes(status)) return C.green;
  if (status === "DEMO_MODE") return C.amber;
  if (status === "ERROR") return C.red;
  return C.dim;
}

// Honest, at-a-glance classification of each integration so a live connection,
// a simulation, and a built-in/ready component are never mistaken for each other.
const PROVIDER_MODE: Record<string, { label: string; color: string }> = {
  ring: { label: "SIMULATED", color: C.amber },
  bedrock: { label: "LIVE · AWS", color: C.green },
  swarmops: { label: "BUILT-IN", color: C.teal },
  alexa_mcp: { label: "READY", color: C.blue },
};

export default function SentinelPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [demo, setDemo] = useState<Demo | null>(null);
  const [approval, setApproval] = useState<"idle" | "pending" | "approved" | "rejected">("idle");
  const [duplicate, setDuplicate] = useState<boolean | null>(null);
  const [execId, setExecId] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("Press RUN SECURITY SCENARIO to replay a real after-hours entrance incident.");

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
    setExecId(null);
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
    setExecId(null);
    setNote("Scenario reset. Press RUN SECURITY SCENARIO to begin again.");
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
      if (kind === "approve") setExecId((data as { execution_id?: string }).execution_id ?? null);
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
            <h1 style={{ margin: "2px 0 0", fontSize: 26, fontWeight: 700 }}>AI Security Officer for Ring</h1>
            <div style={{ margin: "6px 0 0", fontSize: 16, fontWeight: 800 }}>
              <span style={{ color: C.teal }}>AI-powered security decisions.</span>{" "}
              <span style={{ color: C.text }}>Human-controlled authority.</span>
            </div>
            <p style={{ margin: "6px 0 0", fontSize: 14, color: "#cdd8ee", maxWidth: 580, lineHeight: 1.5 }}>
              Turns a Ring camera from a device that only <i>watches</i> into an officer that
              understands the scene, enforces security policy, and acts only with human approval.
            </p>
            <div style={{ color: C.dim, fontSize: 13, marginTop: 8 }}>
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
              const role = { ring: "Eyes", bedrock: "Understanding", swarmops: "Authority", alexa_mcp: "Approvals" }[k];
              const mode = PROVIDER_MODE[k];
              return (
                <div key={k} style={{ background: C.panel, border: `1px solid ${C.edge}`, borderRadius: 10, padding: "12px 14px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, letterSpacing: 1.5, color: C.dim }}>{name} <span style={{ color: "#6f81a6" }}>· {role}</span></span>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 10, fontWeight: 800,
                      letterSpacing: 0.5, color: mode.color, border: `1px solid ${mode.color}`, borderRadius: 999, padding: "2px 7px" }}>
                      <span style={{ width: 6, height: 6, borderRadius: "50%", background: mode.color }} />
                      {mode.label}
                    </span>
                  </div>
                  <div style={{ fontWeight: 800, fontSize: 17, marginTop: 8, color: providerColor(p.status) }}>{p.status}</div>
                  <div style={{ fontSize: 12, color: C.dim, marginTop: 3, lineHeight: 1.35 }}>{p.detail}</div>
                </div>
              );
            })}
        </div>

        {/* Guided demo controls */}
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 20, flexWrap: "wrap" }}>
          <button onClick={start} disabled={busy} style={primaryBtn(C.teal, busy)}>▶ RUN SECURITY SCENARIO</button>
          <button onClick={reset} disabled={busy} style={ghostBtn(busy)}>RESET</button>
          <span style={{ color: "#c3d0e8", fontSize: 13 }}>{note}</span>
        </div>

        {/* Pipeline */}
        <Pipeline stage={pipelineStage} />

        {/* Idle: entrance monitor so the officer is visibly "on watch" pre-demo */}
        {!demo && <EntranceMonitor />}

        {demo && (
          <>
            {/* Incident card + live entrance feed */}
            <section style={{ ...card(), borderColor: C.red }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 13, letterSpacing: 1.5, color: C.red, fontWeight: 800 }}>HIGH-RISK ENTRANCE ACTIVITY</span>
                  <span style={{ fontSize: 11, fontWeight: 800, color: C.amber, border: `1px solid ${C.amber}`, borderRadius: 6, padding: "2px 8px" }}>AFTER HOURS</span>
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>23:42</div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) 2fr", gap: 12, marginTop: 12 }}>
                <CameraPanel alert />
                <div>
                  <div style={{ fontSize: 13, color: C.text }}>
                    Motion ×{demo.ring_events.length} · person present · prolonged &amp; repeated activity
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10, marginTop: 12 }}>
                    <Fact k="BUILDING" v="CLOSED" tone={C.red} />
                    <Fact k="EXPECTED VISITOR" v="NONE" tone={C.red} />
                    <Fact k="ACCESS REQUEST" v="NONE" tone={C.red} />
                    <Fact k="CREDENTIAL" v="NONE" tone={C.red} />
                  </div>
                  <div style={{ marginTop: 12, display: "inline-flex", alignItems: "baseline", gap: 8,
                    padding: "8px 16px", borderRadius: 10, border: `1px solid ${C.red}`, background: "rgba(248,113,113,0.10)" }}>
                    <span style={{ fontSize: 12, letterSpacing: 1.5, color: C.dim }}>RISK</span>
                    <span style={{ fontSize: 28, fontWeight: 900, color: C.red, fontVariantNumeric: "tabular-nums" }}>{demo.incident.risk.risk_score}</span>
                    <span style={{ fontSize: 14, color: C.dim }}>/ 100</span>
                    <span style={{ fontSize: 16, fontWeight: 800, color: C.red, marginLeft: 4 }}>{demo.incident.risk.risk_level}</span>
                  </div>
                </div>
              </div>
            </section>

            {/* CENTERPIECE: AI recommends grant → DENIED */}
            <section style={{ ...card(), borderColor: C.red, background: "rgba(248,113,113,0.06)" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 16, alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.blue }}>AI PROPOSED ACTION</div>
                  <div style={{ fontSize: 20, fontWeight: 800, marginTop: 6 }}>GRANT TEMPORARY ACCESS</div>
                  <div style={{ fontSize: 12, color: C.amber, marginTop: 4 }}>Untrusted recommendation · policy validation required</div>
                </div>
                <div style={{ fontSize: 26, color: C.dim }}>→</div>
                <div>
                  <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.dim }}>SWARMOPS POLICY</div>
                  <div style={{ fontSize: 38, fontWeight: 900, color: C.red, marginTop: 2, letterSpacing: 1,
                    textShadow: "0 0 18px rgba(248,113,113,0.45)" }}>DENIED</div>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 18, color: C.text, fontSize: 13 }}>
                    {demo.centerpiece.reason_codes.map((c) => (
                      <li key={c}>{REASON_LABEL[c] ?? c}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div style={{ marginTop: 14, textAlign: "center" }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: C.text }}>
                  &ldquo;AI recommended access. Security policy stopped it.&rdquo;
                </div>
                <div style={{ fontSize: 12, color: C.dim, marginTop: 4 }}>
                  Deterministic decision — the AI cannot override it.
                </div>
              </div>
              {/* The safe alternative Sentinel took instead — kept visually prominent */}
              <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
                justifyContent: "center", padding: "10px 16px", borderRadius: 10,
                background: "rgba(52,211,153,0.10)", border: `1px solid ${C.green}` }}>
                <span style={{ fontSize: 12, fontWeight: 800, letterSpacing: 1, color: C.green }}>SAFE ACTION INSTEAD</span>
                <span style={{ color: C.dim }}>→</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: C.text }}>
                  Notify the security officer (human-approved) — never open the door
                </span>
              </div>
            </section>

            {/* SECOND ACTION: send warning → human approval */}
            <section style={card()}>
              <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.blue }}>AI PROPOSED ACTION</div>
                  <div style={{ fontSize: 18, fontWeight: 800, marginTop: 4 }}>SEND WARNING</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 12, letterSpacing: 1.5, color: C.dim }}>SWARMOPS</div>
                  <div style={{ fontSize: 16, fontWeight: 800,
                    color: approval === "approved" ? C.green : approval === "rejected" ? C.red : C.amber }}>
                    {approval === "approved"
                      ? "APPROVED & EXECUTED ✓"
                      : approval === "rejected"
                        ? "REJECTED"
                        : "HUMAN APPROVAL REQUIRED"}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                {approval === "pending" && (
                  <>
                    <span style={{ color: C.dim, fontSize: 13 }}>Review proposed security action:</span>
                    <button onClick={() => decide("approve")} disabled={busy} style={primaryBtn(C.green, busy)}>APPROVE</button>
                    <button onClick={() => decide("reject")} disabled={busy} style={dangerBtn(busy)}>REJECT</button>
                  </>
                )}
                {approval === "approved" && (
                  <>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: "12px 16px",
                      borderRadius: 10, background: "rgba(52,211,153,0.10)", border: `1px solid ${C.green}`, minWidth: 260 }}>
                      <Check title="WARNING APPROVED" sub="Approved by Security Officer" />
                      <Check title="ACTION EXECUTED" sub="Warning dispatched" />
                      <Check title="EXACTLY ONCE" sub={`Execution ID: ${execId ?? "—"}`} />
                      <Check title="AUDIT RECORDED" sub="Immutable incident timeline" />
                    </div>
                    <button onClick={replay} disabled={busy} style={ghostBtn(busy)}>Replay the exact same request</button>
                    {duplicate === true && (
                      <div style={{ padding: "12px 16px", borderRadius: 10, background: "rgba(251,191,36,0.12)", border: `1px solid ${C.amber}`, minWidth: 260 }}>
                        <div style={{ color: C.amber, fontWeight: 800, fontSize: 15 }}>🛡 DUPLICATE EXECUTION BLOCKED</div>
                        <div style={{ fontSize: 12, color: C.dim, marginTop: 4 }}>Existing execution detected — no second warning sent.</div>
                      </div>
                    )}
                  </>
                )}
                {approval === "rejected" && (
                  <span style={{ color: C.red, fontWeight: 700 }}>Warning rejected — no action taken.</span>
                )}
              </div>
            </section>

            {/* Closing result — the whole story in one line */}
            {approval === "approved" && (
              <section style={{ ...card(), borderColor: C.green, background: "rgba(52,211,153,0.07)" }}>
                <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", alignItems: "stretch", gap: 10 }}>
                  <ResultPart icon="🚨" tone={C.red} label="THREAT DETECTED" sub="After-hours entrance · risk 87" />
                  <span style={{ alignSelf: "center", color: C.dim, fontSize: 20 }}>→</span>
                  <ResultPart icon="🚫" tone={C.amber} label="UNSAFE ACTION DENIED" sub="AI-proposed access blocked by policy" />
                  <span style={{ alignSelf: "center", color: C.dim, fontSize: 20 }}>→</span>
                  <ResultPart icon="📣" tone={C.green} label="SECURITY NOTIFIED" sub="Human-approved · executed exactly once" />
                </div>
              </section>
            )}

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
                      t={tlTime(t.action)}
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
function CameraPanel({ alert = false, time = "23:42" }: { alert?: boolean; time?: string }) {
  const accent = alert ? C.red : C.teal;
  const clock = alert ? time : "23:30";
  return (
    <div style={{ position: "relative", borderRadius: 12, border: `1px solid ${alert ? C.red : C.edge}`,
      background: "#060b14", minHeight: 196, overflow: "hidden" }}>
      {/* ---- Simulated night-entrance scene (drawn, labelled SIMULATED) ---- */}
      <svg viewBox="0 0 320 196" preserveAspectRatio="xMidYMid slice"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#0c1a33" />
            <stop offset="1" stopColor="#060b14" />
          </linearGradient>
          <radialGradient id="porch" cx="50%" cy="34%" r="46%">
            <stop offset="0" stopColor={alert ? "rgba(255,170,150,0.26)" : "rgba(150,200,255,0.20)"} />
            <stop offset="1" stopColor="rgba(0,0,0,0)" />
          </radialGradient>
        </defs>
        <rect width="320" height="196" fill="url(#sky)" />
        {/* ground */}
        <rect y="156" width="320" height="40" fill="#0a1120" />
        <line x1="0" y1="156" x2="320" y2="156" stroke="#17243d" strokeWidth="1" />
        {/* wall + door frame */}
        <rect x="116" y="40" width="88" height="116" fill="#0e1729" stroke="#1d2c49" />
        <rect x="128" y="52" width="64" height="104" fill="#0a1220" stroke="#1d2c49" />
        <circle cx="184" cy="108" r="2.4" fill="#33466b" />
        {/* porch light pool */}
        <rect width="320" height="196" fill="url(#porch)" />
        {/* hooded figure at the door (the after-hours subject) */}
        <g opacity={alert ? 1 : 0.28}>
          <ellipse cx="160" cy="156" rx="26" ry="5" fill="rgba(0,0,0,0.55)" />
          <path d="M143 156 Q143 112 160 106 Q177 112 177 156 Z" fill="#0b111d" />
          <circle cx="160" cy="98" r="9.5" fill="#0b111d" />
          <path d="M150 99 Q160 86 170 99 L167 100 Q160 92 153 100 Z" fill="#111a2b" />
        </g>
        {/* detection box + label, only during the incident */}
        {alert && (
          <g>
            <rect x="138" y="84" width="44" height="76" fill="none" stroke={C.red} strokeWidth="1.5" strokeDasharray="5 3" />
            <rect x="138" y="74" width="60" height="11" rx="2" fill={C.red} />
            <text x="141" y="82.5" fontSize="7.5" fontWeight="700" fill="#2a0708" fontFamily="monospace">PERSON 92%</text>
          </g>
        )}
      </svg>

      {/* scanlines + vignette for a CCTV feel */}
      <div aria-hidden style={{ position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "repeating-linear-gradient(0deg, rgba(255,255,255,0.035) 0px, rgba(255,255,255,0.035) 1px, transparent 1px, transparent 3px)" }} />
      {alert && (
        <div aria-hidden style={{ position: "absolute", inset: 0, pointerEvents: "none",
          background: "radial-gradient(circle at 50% 42%, rgba(248,113,113,0.12), rgba(248,113,113,0.03) 58%, transparent 72%)" }} />
      )}

      {/* corner brackets */}
      {[0, 1, 2, 3].map((i) => (
        <span key={i} aria-hidden style={{
          position: "absolute", width: 16, height: 16,
          borderTop: i < 2 ? `2px solid ${accent}` : "none",
          borderBottom: i >= 2 ? `2px solid ${accent}` : "none",
          borderLeft: i % 2 === 0 ? `2px solid ${accent}` : "none",
          borderRight: i % 2 === 1 ? `2px solid ${accent}` : "none",
          top: i < 2 ? 10 : "auto", bottom: i >= 2 ? 10 : "auto",
          left: i % 2 === 0 ? 10 : "auto", right: i % 2 === 1 ? 10 : "auto", opacity: 0.85 }} />
      ))}

      {/* top overlay: camera id + REC/LIVE */}
      <div style={{ position: "absolute", top: 12, left: 14, right: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, letterSpacing: 1.5, color: "#c3d0e8", textShadow: "0 1px 3px #000" }}>FRONT ENTRANCE</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 800, color: accent, textShadow: "0 1px 3px #000" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: accent, boxShadow: `0 0 8px ${accent}` }} />
          {alert ? "● REC · INCIDENT" : "LIVE"}
        </span>
      </div>

      {/* bottom overlay: SIMULATED FEED label + camera id + timestamp */}
      <div style={{ position: "absolute", bottom: 10, left: 14, right: 14,
        display: "flex", justifyContent: "space-between", alignItems: "flex-end", fontVariantNumeric: "tabular-nums" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 10, fontWeight: 800, letterSpacing: 0.5,
          color: "#0a1120", background: "rgba(166,182,214,0.9)", borderRadius: 4, padding: "2px 7px" }}>
          ◉ SIMULATED FEED
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, color: "#dce5f5", textShadow: "0 1px 3px #000" }}>
          {clock} {alert && <span style={{ color: C.amber }}>· LOW LIGHT</span>}
        </span>
      </div>
    </div>
  );
}

function EntranceMonitor() {
  return (
    <section style={{ ...card(), marginTop: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(240px, 1fr) 1fr", gap: 14 }}>
        <CameraPanel />
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 8 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: C.green, boxShadow: `0 0 10px ${C.green}` }} />
            <span style={{ fontWeight: 800, color: C.green, letterSpacing: 0.5 }}>MONITORING ENTRANCE</span>
          </div>
          <div style={{ fontSize: 22, fontWeight: 800 }}>No active incident</div>
          <div style={{ fontSize: 13, color: C.dim }}>
            Ring feed connected (simulator). Bedrock, SwarmOps policy, and human approval are on standby.
            Press <b style={{ color: C.teal }}>RUN SECURITY SCENARIO</b> to replay a real after-hours entrance incident.
          </div>
        </div>
      </div>
    </section>
  );
}

function ResultPart({ icon, tone, label, sub }: { icon: string; tone: string; label: string; sub: string }) {
  return (
    <div style={{ flex: "1 1 180px", minWidth: 180, textAlign: "center", padding: "12px 14px",
      borderRadius: 12, border: `1px solid ${tone}`, background: "rgba(255,255,255,0.02)" }}>
      <div style={{ fontSize: 22 }}>{icon}</div>
      <div style={{ fontSize: 15, fontWeight: 900, letterSpacing: 0.5, color: tone, marginTop: 4 }}>{label}</div>
      <div style={{ fontSize: 12, color: C.dim, marginTop: 3, lineHeight: 1.35 }}>{sub}</div>
    </div>
  );
}

function Fact({ k, v, tone }: { k: string; v: string; tone: string }) {
  return (
    <div style={{ background: "#0d1526", border: `1px solid ${C.edge}`, borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ fontSize: 11, letterSpacing: 1, color: C.dim }}>{k}</div>
      <div style={{ fontWeight: 800, color: tone, marginTop: 4 }}>{v}</div>
    </div>
  );
}

function Check({ title, sub }: { title: string; sub: string }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
      <span style={{ color: C.green, fontWeight: 800 }}>✓</span>
      <span style={{ fontWeight: 800, color: C.text, fontSize: 13, letterSpacing: 0.3 }}>{title}</span>
      <span style={{ fontSize: 11, color: C.dim }}>{sub}</span>
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
        const done = i < stage;
        const current = stage > 0 && i === stage; // the step awaiting attention right now
        const accent = done ? C.teal : current ? C.amber : C.edge;
        const labelColor = done ? C.teal : current ? C.amber : C.text;
        return (
          <div key={s.top} style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 150 }}>
            <div style={{ flex: 1, textAlign: "center", padding: "12px 8px", borderRadius: 10,
              border: `1px solid ${accent}`,
              background: done ? "rgba(45,212,191,0.10)" : current ? "rgba(251,191,36,0.10)" : C.panel }}>
              <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: 1, color: labelColor }}>
                {done ? "✓ " : current ? "● " : ""}{s.top}
              </div>
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
