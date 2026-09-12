"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Incident = {
  incident_id: string;
  status: string;
  severity: string;
  risk: { risk_score: number; risk_level: string };
};

type Propose = { action_id: string; decision: string; approval_id: string | null; executed: boolean };
type ApiError = { error?: { code?: string } };

async function call(path: string, body?: unknown): Promise<{ ok: boolean; data: unknown }> {
  const res = await fetch(`${API_URL}${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, data };
}

function errCode(data: unknown): string {
  return (data as ApiError)?.error?.code ?? "denied";
}

export function SentinelConsole() {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [approvalId, setApprovalId] = useState<string | null>(null);
  const [line, setLine] = useState<string>("Load an incident, then propose an action.");
  const [proof, setProof] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const { ok, data } = await call("/api/sentinel/incident");
    if (ok) setIncident(data as Incident);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const propose = async () => {
    setBusy(true);
    setApprovalId(null);
    const { ok, data } = await call("/api/sentinel/propose", {
      action_type: "SEND_WARNING",
      actor_id: "owner-alex",
    });
    if (ok) {
      const p = data as Propose;
      setApprovalId(p.approval_id);
      setLine(`Proposed SEND_WARNING → ${p.decision}. Awaiting a security officer's approval.`);
    } else {
      setLine(`Error: ${errCode(data)}`);
    }
    setBusy(false);
  };

  const resolve = async (path: string, actor: string, label: string) => {
    if (!approvalId) return;
    setBusy(true);
    const { ok, data } = await call(`/api/sentinel/${path}`, { approval_id: approvalId, actor_id: actor });
    if (ok) {
      const execId = (data as { execution_id?: string }).execution_id ?? "ok";
      setLine(
        path === "approve"
          ? `${label}: warning executed exactly once (execution ${execId}).`
          : `${label}: action rejected.`,
      );
      if (path === "approve") setApprovalId(null);
    } else {
      setLine(`${label} BLOCKED by SwarmOps: ${errCode(data)}`);
    }
    setBusy(false);
  };

  const runProof = async () => {
    setBusy(true);
    const { ok, data } = await call("/api/sentinel/winner-proof");
    if (ok) {
      const p = data as { executed_count: number; duplicate_prevented: boolean; first_execution_id: string };
      setProof(
        `Warning approved & executed once (${p.first_execution_id}). Replayed the exact same request → ` +
          `${p.duplicate_prevented ? "DUPLICATE EXECUTION PREVENTED" : "?"}. Total executions: ${p.executed_count}.`,
      );
    } else {
      setProof("winner proof unavailable");
    }
    setBusy(false);
  };

  return (
    <section
      style={{
        margin: "16px 0",
        padding: 16,
        borderRadius: 12,
        border: "1px solid rgba(148,163,184,0.35)",
        background: "rgba(15,23,42,0.02)",
      }}
    >
      <div style={{ fontSize: 11, letterSpacing: 1, color: "#64748b" }}>SENTINEL · OFFICER CONSOLE</div>
      <strong style={{ fontSize: 15 }}>Human approval — same authority as Alexa+</strong>
      {incident ? (
        <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>
          Incident <b>{incident.incident_id}</b> · status {incident.status} · risk{" "}
          <b>{incident.risk.risk_level}</b> ({incident.risk.risk_score}/100)
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        <button onClick={propose} disabled={busy} style={btn("#2563eb")}>
          Propose SEND_WARNING (owner)
        </button>
        <button onClick={() => resolve("approve", "officer-sam", "Officer approves")} disabled={busy || !approvalId} style={btn("#16a34a", !approvalId)}>
          Approve (security officer)
        </button>
        <button onClick={() => resolve("reject", "officer-sam", "Officer rejects")} disabled={busy || !approvalId} style={btn("#b45309", !approvalId)}>
          Reject (security officer)
        </button>
        <button onClick={() => resolve("approve", "guest-01", "Guest bypass")} disabled={busy || !approvalId} style={btn("#dc2626", !approvalId)}>
          Try bypass (guest approves)
        </button>
      </div>

      <div style={{ marginTop: 12, fontSize: 13, color: "#0f172a" }}>{line}</div>

      <div style={{ marginTop: 12, borderTop: "1px dashed rgba(148,163,184,0.4)", paddingTop: 12 }}>
        <button onClick={runProof} disabled={busy} style={btn("#0f766e")}>
          Winner proof: execute, then replay same request
        </button>
        {proof ? (
          <div
            style={{
              marginTop: 8,
              padding: "8px 10px",
              borderRadius: 8,
              border: "1px solid #0f766e",
              background: "rgba(15,118,110,0.08)",
              fontSize: 13,
              color: "#0f172a",
            }}
          >
            {proof}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function btn(color: string, disabled = false): React.CSSProperties {
  return {
    padding: "8px 12px",
    borderRadius: 8,
    border: `1px solid ${color}`,
    background: disabled ? "rgba(148,163,184,0.25)" : color,
    color: disabled ? "#64748b" : "white",
    cursor: disabled ? "default" : "pointer",
    fontSize: 12,
  };
}
