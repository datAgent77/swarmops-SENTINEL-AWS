"use client";

import type { Metrics } from "../lib/types";
import { AnimatedNumber } from "./AnimatedNumber";

export function MetricsRail({
  metrics,
  statusLabel,
  provider,
  reducedMotion,
}: {
  metrics: Metrics | undefined;
  statusLabel: string;
  provider: string | null;
  reducedMotion: boolean;
}) {
  const cost = metrics ? Number(metrics.total_cost_usd) : 0;
  const budget = metrics ? Number(metrics.budget_usd) : 0;
  const tokens = metrics ? metrics.input_tokens + metrics.output_tokens : 0;
  const budgetPct = budget > 0 ? Math.min(100, (cost / budget) * 100) : 0;

  return (
    <section className="rail" aria-label="Live mission metrics">
      <div className="rail-cell">
        <span>Mission</span>
        <strong>{statusLabel}</strong>
      </div>
      <div className="rail-cell">
        <span>Events</span>
        <strong>
          <AnimatedNumber value={metrics?.events ?? 0} reducedMotion={reducedMotion} />
        </strong>
      </div>
      <div className={`rail-cell ${metrics?.blocked ? "danger" : ""}`}>
        <span>Blocked</span>
        <strong>
          <AnimatedNumber value={metrics?.blocked ?? 0} reducedMotion={reducedMotion} />
        </strong>
      </div>
      <div className={`rail-cell ${metrics?.approvals ? "warn" : ""}`}>
        <span>Approvals</span>
        <strong>
          <AnimatedNumber value={metrics?.approvals ?? 0} reducedMotion={reducedMotion} />
        </strong>
      </div>
      <div className="rail-cell wide">
        <span>Cost / Budget</span>
        <strong>
          <AnimatedNumber value={cost} decimals={2} prefix="$" reducedMotion={reducedMotion} /> / ${budget.toFixed(2)}
        </strong>
        <div className="rail-bar">
          <div className={`rail-bar-fill ${budgetPct >= 85 ? "danger" : budgetPct >= 60 ? "warn" : ""}`} style={{ width: `${budgetPct}%` }} />
        </div>
      </div>
      <div className="rail-cell">
        <span>LLM Tokens</span>
        <strong>
          <AnimatedNumber value={tokens} reducedMotion={reducedMotion} />
        </strong>
        <em className="rail-sub">{metrics?.llm_calls ?? 0} calls{provider ? ` · ${provider}` : ""}</em>
      </div>
    </section>
  );
}
