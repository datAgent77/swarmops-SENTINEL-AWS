"use client";

import type { EvolutionCard, MissionSummary } from "../lib/types";

function badge(score: number): { label: string; cls: string } {
  if (score >= 90) return { label: "Elite", cls: "good" };
  if (score >= 80) return { label: "Strong", cls: "good" };
  if (score >= 70) return { label: "Solid", cls: "ok" };
  return { label: "Developing", cls: "low" };
}

export function EvolutionPanel({
  evolution,
  summary,
  showSummary,
  onDecideVersion,
}: {
  evolution: EvolutionCard[];
  summary: MissionSummary | null;
  showSummary: boolean;
  onDecideVersion: (versionId: string, action: "approve" | "reject") => void;
}) {
  if (evolution.length === 0) return null;

  return (
    <section className="panel evo-panel">
      <div className="panel-head">
        <h2>Self-Evolving Workforce</h2>
        <span>versions · performance · governed upgrades</span>
      </div>

      {showSummary && summary ? (
        <div className="summary-strip">
          <Stat label="Top performer" value={summary.top_performer} tone="ok" />
          <Stat label="Most improved" value={summary.most_improved} tone="accent" />
          <Stat label="Highest cost" value={summary.highest_cost_agent} />
          <Stat label="Highest risk" value={summary.highest_risk_agent} tone="warn" />
          <Stat label="Biggest opportunity" value={summary.biggest_opportunity} />
        </div>
      ) : null}

      <div className="evo-grid">
        {evolution.map((card) => {
          const b = badge(card.performance_score);
          return (
            <div key={card.agent_key} className={`evo-card ${card.pending_version ? "pending" : ""}`}>
              <div className="evo-head">
                <strong>{card.name}</strong>
                <span className="evo-ver">v{card.current_version}</span>
              </div>
              <div className="evo-scores">
                <div>
                  <em>Performance</em>
                  <b>{card.performance_score}</b>
                </div>
                <div>
                  <em>Improvement</em>
                  <b className={card.improvement_score ? "pos" : ""}>
                    {card.improvement_score ? `+${card.improvement_score}` : "—"}
                  </b>
                </div>
                <span className={`perf-badge ${b.cls}`}>{b.label}</span>
                <span className="evo-trend">
                  {card.trend === "up" ? "▲" : card.trend === "down" ? "▼" : "→"}
                </span>
              </div>

              {card.pending_version ? (
                <div className="evo-pending">
                  <span className="evo-tag">⚖ Upgrade pending governance</span>
                  <p>{card.pending_version.improvements[0]?.suggestion}</p>
                  <div className="evo-actions">
                    <button className="btn ghost-danger sm" onClick={() => onDecideVersion(card.pending_version!.id, "reject")}>
                      Reject
                    </button>
                    <button className="btn solid-ok sm" onClick={() => onDecideVersion(card.pending_version!.id, "approve")}>
                      Approve → v{card.pending_version.version}
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | null; tone?: string }) {
  return (
    <div className="summary-stat">
      <span>{label}</span>
      <strong className={tone ? `t-${tone}` : ""}>{value ?? "—"}</strong>
    </div>
  );
}
