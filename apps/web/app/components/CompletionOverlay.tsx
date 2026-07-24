"use client";

import { useEffect } from "react";
import type { Metrics, MissionSummary } from "../lib/types";

const OUTCOME: Record<string, { label: string; tone: string; icon: string }> = {
  completed: { label: "Mission complete", tone: "ok", icon: "✓" },
  rejected: { label: "Mission stopped by governance", tone: "warn", icon: "⚖" },
  blocked: { label: "Mission blocked", tone: "danger", icon: "⛔" },
  failed: { label: "Mission failed", tone: "danger", icon: "!" },
};

export function CompletionOverlay({
  status,
  metrics,
  summary,
  reducedMotion,
  onClose,
}: {
  status: string;
  metrics: Metrics | undefined;
  summary: MissionSummary | null;
  reducedMotion: boolean;
  onClose: () => void;
}) {
  const o = OUTCOME[status] ?? OUTCOME.completed;
  const cost = metrics ? Number(metrics.total_cost_usd) : 0;
  const tokens = metrics ? metrics.input_tokens + metrics.output_tokens : 0;

  // Dismiss on Escape (WCAG dialog behavior).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="overlay-scrim" role="dialog" aria-modal="true" aria-label={o.label} onClick={onClose}>
      <div className={`overlay-card t-${o.tone} ${reducedMotion ? "" : "pop"}`} onClick={(e) => e.stopPropagation()}>
        <div className={`overlay-badge t-${o.tone}`} aria-hidden>
          {o.icon}
        </div>
        <h2>{o.label}</h2>
        <p className="overlay-sub">Full audit trail persisted. Governance enforced every step.</p>

        <div className="overlay-stats">
          <div>
            <span>Events</span>
            <strong>{metrics?.events ?? 0}</strong>
          </div>
          <div>
            <span>Blocked</span>
            <strong>{metrics?.blocked ?? 0}</strong>
          </div>
          <div>
            <span>Approvals</span>
            <strong>{metrics?.approvals ?? 0}</strong>
          </div>
          <div>
            <span>Cost</span>
            <strong>${cost.toFixed(2)}</strong>
          </div>
          <div>
            <span>Tokens</span>
            <strong>{tokens.toLocaleString()}</strong>
          </div>
        </div>

        {summary ? (
          <div className="overlay-summary">
            {summary.top_performer ? (
              <span>
                Top performer <strong>{summary.top_performer}</strong>
              </span>
            ) : null}
            {summary.most_improved ? (
              <span>
                Most improved <strong>{summary.most_improved}</strong>
              </span>
            ) : null}
            {summary.biggest_opportunity ? (
              <span>
                Opportunity <strong>{summary.biggest_opportunity}</strong>
              </span>
            ) : null}
          </div>
        ) : null}

        <button className="btn solid-accent overlay-close" onClick={onClose} autoFocus>
          Review mission
        </button>
      </div>
    </div>
  );
}
