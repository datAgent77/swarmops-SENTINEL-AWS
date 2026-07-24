// Pure selectors that turn raw events + snapshot + evolution into view models.
import type { AgentItem, AgentView, EventItem, EvolutionCard } from "./types";
import { ROSTER_KEYS } from "./types";

export type Severity = "info" | "success" | "warning" | "danger" | "muted";

export type EventMeta = {
  icon: string;
  severity: Severity;
  governance: boolean;
  kind: string; // css class hook
};

// Classify an event for the timeline: icon, severity, whether it's a
// governance decision, and a css kind.
export function eventMeta(item: EventItem): EventMeta {
  const t = item.type;

  if (t === "agent.thinking") return { icon: "◍", severity: "muted", governance: false, kind: "thinking" };
  if (t === "agent.reasoning") return { icon: "❖", severity: "info", governance: false, kind: "reasoning" };
  if (t === "agent.message") return { icon: "💬", severity: "info", governance: false, kind: "message" };

  // A governance DECISION is a neutral audit record (it may say allow / block /
  // approval_required in its text). The actual enforcement gets its own event
  // (governance.blocked / approval.requested) with the strong styling below, so
  // one blocked action shows exactly one "blocked" badge — matching the metric.
  if (t === "governance.decision") return { icon: "⚖", severity: "info", governance: true, kind: "governance" };
  if (
    t === "governance.blocked" ||
    t === "approval.rejected" ||
    t === "mission.rejected" ||
    t === "mission.failed" ||
    t === "agent.quarantined"
  ) {
    return { icon: "⛔", severity: "danger", governance: true, kind: "block" };
  }
  if (t === "approval.requested" || t === "mission.paused") {
    return { icon: "⚖", severity: "warning", governance: true, kind: "approval" };
  }
  if (t === "approval.granted") return { icon: "✓", severity: "success", governance: true, kind: "ok" };
  if (t === "deploy.succeeded" || t === "qa.passed" || t === "mission.completed") {
    return { icon: "✓", severity: "success", governance: false, kind: "ok" };
  }
  if (t === "qa.issue_found") return { icon: "!", severity: "warning", governance: false, kind: "warn" };
  if (t === "issue.fixed") return { icon: "✎", severity: "info", governance: false, kind: "fix" };
  if (t === "cost.recorded" || t === "budget.reviewed") return { icon: "$", severity: "muted", governance: false, kind: "cost" };
  if (t === "mission.started") return { icon: "▶", severity: "info", governance: false, kind: "start" };
  if (t === "sponsors.active") return { icon: "◆", severity: "info", governance: false, kind: "sponsors" };
  if (t === "mission.published") return { icon: "↗", severity: "success", governance: false, kind: "publish" };
  if (t.startsWith("agent.version") || t.startsWith("agent.improvement") || t.startsWith("agent.evaluation")) {
    return { icon: "↗", severity: "info", governance: false, kind: "evolve" };
  }
  return { icon: "•", severity: "muted", governance: false, kind: "" };
}

// Merge the roster, evolution cards, and event telemetry into one view per agent.
export function deriveAgents(
  roster: AgentItem[],
  evolution: EvolutionCard[],
  events: EventItem[],
  activeKey: string | null,
): AgentView[] {
  const byKey = new Map(roster.map((a) => [a.key, a]));
  const evoByKey = new Map(evolution.map((c) => [c.agent_key, c]));

  // Per-agent telemetry from the event stream.
  const cost = new Map<string, number>();
  const model = new Map<string, string>();
  const provider = new Map<string, string>();
  const lastReasoning = new Map<string, string>();
  const lastActivity = new Map<string, string>();

  for (const e of events) {
    const k = e.actor_id;
    if (e.type === "agent.reasoning") {
      const c = Number(e.payload?.cost_usd ?? 0);
      cost.set(k, (cost.get(k) ?? 0) + (Number.isFinite(c) ? c : 0));
      if (e.payload?.model) model.set(k, String(e.payload.model));
      if (e.payload?.provider) provider.set(k, String(e.payload.provider));
      lastReasoning.set(k, e.message);
    }
    if (e.type === "cost.recorded") {
      const c = Number(e.payload?.amount_usd ?? e.payload?.amount ?? 0);
      if (Number.isFinite(c) && c > 0) cost.set(k, (cost.get(k) ?? 0) + c);
    }
    // A short "current task" label from the latest substantive event.
    if (!["cost.recorded", "agent.thinking"].includes(e.type)) {
      lastActivity.set(k, e.message);
    }
  }

  return ROSTER_KEYS.map((key) => {
    const a = byKey.get(key);
    const evo = evoByKey.get(key);
    return {
      key,
      name: a?.name ?? key,
      role: a?.role ?? "",
      status: a?.status ?? "idle",
      version: evo?.current_version ?? "1.0",
      score: evo ? evo.performance_score : null,
      trend: evo?.trend ?? "flat",
      model: model.get(key) ?? null,
      provider: provider.get(key) ?? null,
      costUsd: cost.get(key) ?? 0,
      task: lastActivity.get(key) ?? null,
      reasoning: lastReasoning.get(key) ?? null,
      pending: evo?.pending_version ?? null,
      active: activeKey === key,
    };
  }).filter((v) => v.name);
}

// Which agent produced the most recent event (drives the active highlight).
export function activeAgentKey(events: EventItem[]): string | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const k = events[i].actor_id;
    if (k && k !== "system") return k;
  }
  return null;
}
