// Shared types for the Living AI Workforce dashboard (Sprint 5).
// All shapes mirror the backend /api responses (snake_case).

export type EventItem = {
  id: string;
  seq: number;
  type: string;
  actor_id: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AgentItem = {
  id: string;
  key: string;
  name: string;
  role: string;
  team: string;
  status: string;
};

export type PendingApproval = {
  id: string;
  tool: string;
  resource: string | null;
  reason: string;
  policy_id: string;
  risk_score: number;
};

export type Metrics = {
  events: number;
  blocked: number;
  approvals: number;
  tasks_total: number;
  tasks_done: number;
  total_cost_usd: string;
  budget_usd: string;
  input_tokens: number;
  output_tokens: number;
  llm_calls: number;
};

export type MissionRow = { id: string; objective: string; status: string; created_at: string };

export type Snapshot = {
  mission: { id: string; objective: string; budget_usd: string; status: string };
  agents: AgentItem[];
  pending_approval: PendingApproval | null;
  metrics: Metrics;
};

export type PendingVersion = {
  id: string;
  version: string;
  risk_level: string;
  reason: string;
  improvements: { suggestion: string; expected_impact: string; risk: string }[];
  performance_delta: { score_before?: number; score_after?: number };
};

export type EvolutionCard = {
  agent_key: string;
  name: string;
  current_version: string;
  performance_score: number;
  improvement_score: number;
  trend: string;
  pending_version: PendingVersion | null;
};

export type MissionSummary = {
  top_performer: string | null;
  most_improved: string | null;
  highest_cost_agent: string | null;
  highest_risk_agent: string | null;
  biggest_opportunity: string | null;
};

// A fully-merged view of one agent, assembled from the snapshot, the evolution
// cards, and the derived per-agent telemetry pulled out of the event stream.
export type AgentView = {
  key: string;
  name: string;
  role: string;
  status: string;
  version: string;
  score: number | null;
  trend: string;
  model: string | null;
  provider: string | null;
  costUsd: number;
  task: string | null;
  reasoning: string | null;
  pending: PendingVersion | null;
  active: boolean;
};

export const TERMINAL = new Set(["completed", "rejected", "failed", "blocked"]);

export const STATUS_LABEL: Record<string, string> = {
  created: "Created",
  planning: "Planning",
  assigned: "Assigned",
  running: "Running",
  waiting_approval: "Awaiting approval",
  validating: "Validating",
  completed: "Completed",
  rejected: "Rejected",
  failed: "Failed",
  blocked: "Blocked",
};

// Ordered roster + graph hierarchy. Keys must match the seeded agents.
export const ROSTER_KEYS = ["ceo", "pm", "developer", "security", "qa", "finance"] as const;
