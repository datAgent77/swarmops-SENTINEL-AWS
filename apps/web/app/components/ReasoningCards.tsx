"use client";

import type { AgentView } from "../lib/types";

// Compact "reasoning visibility" cards — a decision-summary surface, NOT raw
// chain-of-thought. Shows the agent's latest reasoning summary plus provider,
// model, and cost telemetry.
export function ReasoningCards({ agents }: { agents: AgentView[] }) {
  const reasoned = agents.filter((a) => a.reasoning);
  if (reasoned.length === 0) {
    return <div className="empty">Agent reasoning will appear here as the mission runs.</div>;
  }
  return (
    <div className="reason-grid">
      {reasoned.map((a) => (
        <article key={a.key} className={`reason-card ${a.active ? "active" : ""}`}>
          <header className="reason-head">
            <span className={`reason-avatar av-${a.key}`} aria-hidden>
              {a.name.slice(0, 1)}
            </span>
            <div>
              <strong>{a.name}</strong>
              <span className="reason-role">{a.role}</span>
            </div>
            {a.provider ? <span className="reason-provider">{a.provider}</span> : null}
          </header>
          <p className="reason-text">{a.reasoning}</p>
          <footer className="reason-foot">
            <span>{a.model ?? "—"}</span>
            <span className="reason-cost">${a.costUsd.toFixed(2)}</span>
          </footer>
        </article>
      ))}
    </div>
  );
}
