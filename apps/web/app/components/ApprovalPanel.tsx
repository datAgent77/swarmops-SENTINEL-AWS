"use client";

import type { PendingApproval } from "../lib/types";

// A focused side panel for a governance approval gate. Slides in when the
// mission is paused awaiting a human decision.
export function ApprovalPanel({
  pending,
  deciding,
  onDecide,
}: {
  pending: PendingApproval;
  deciding: boolean;
  onDecide: (action: "approve" | "reject") => void;
}) {
  const risk = Math.max(0, Math.min(100, pending.risk_score));
  const tone = risk >= 80 ? "danger" : risk >= 50 ? "warn" : "ok";

  return (
    <aside className="approval-panel" role="dialog" aria-label="Governance approval required" aria-modal="false">
      <div className="ap-tag">⚖ Human approval required</div>
      <h3 className="ap-title">
        {pending.tool}
        {pending.resource ? <span className="ap-res"> → {pending.resource}</span> : null}
      </h3>
      <p className="ap-reason">{pending.reason}</p>

      <div className="ap-risk">
        <div className="ap-risk-head">
          <span>Risk score</span>
          <strong className={`t-${tone}`}>{risk}/100</strong>
        </div>
        <div className="ap-risk-track">
          <div className={`ap-risk-fill t-${tone}`} style={{ width: `${risk}%` }} />
        </div>
        <span className="ap-policy">policy · {pending.policy_id}</span>
      </div>

      <div className="ap-actions">
        <button className="btn ghost-danger" disabled={deciding} onClick={() => onDecide("reject")}>
          Reject
        </button>
        <button className="btn solid-ok" disabled={deciding} onClick={() => onDecide("approve")}>
          {deciding ? "Submitting…" : "Approve"}
        </button>
      </div>
    </aside>
  );
}
