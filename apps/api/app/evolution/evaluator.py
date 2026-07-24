"""PerformanceEvaluator — deterministic per-agent evaluation after a mission.

Computes measurable metrics from the mission's persisted events, governance
decisions, tasks, and cost records, derives a 0..100 score, and detects
weaknesses. No randomness, no LLM — evaluation is reproducible and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.models import Agent, CostRecord, Event, GovernanceDecision, Mission, MissionTask
from app.domain.enums import DecisionResult, TaskStatus


@dataclass
class AgentEvaluation:
    metrics: dict
    score: float
    weaknesses: list[dict]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return round(max(lo, min(hi, value)), 2)


class PerformanceEvaluator:
    def evaluate(self, mission: Mission, agent: Agent, events: list[Event],
                 decisions: list[GovernanceDecision], tasks: list[MissionTask],
                 costs: list[CostRecord]) -> AgentEvaluation:
        agent_events = [e for e in events if e.actor_id == agent.key]
        agent_decisions = [d for d in decisions if d.agent_id == agent.id]
        agent_tasks = [t for t in tasks if t.agent_id == agent.id]
        agent_costs = [c for c in costs if c.agent_id == agent.id]

        # --- metrics ---------------------------------------------------------
        total_tasks = len(agent_tasks)
        done_tasks = sum(1 for t in agent_tasks if t.status == TaskStatus.DONE)
        task_success_rate = round(done_tasks / total_tasks, 3) if total_tasks else 1.0

        if len(agent_events) >= 2:
            span = (agent_events[-1].created_at - agent_events[0].created_at).total_seconds()
            completion_latency_ms = int(max(0.0, span) * 1000)
        else:
            completion_latency_ms = 0

        decision_payloads = [e.payload.get("decision", {}) for e in agent_events if "decision" in e.payload]
        confidences = [
            float(d["confidence"]) for d in decision_payloads
            if isinstance(d.get("confidence"), (int, float))
        ]
        reasoning_quality = round(sum(confidences) / len(confidences), 3) if confidences else 0.85

        has_handoff = any("nextAgent" in d and d.get("nextAgent") for d in decision_payloads)
        handoff_quality = 1.0 if has_handoff else (0.8 if decision_payloads else 0.9)

        allowed = sum(1 for d in agent_decisions if d.result == DecisionResult.ALLOW)
        approval_count = sum(1 for d in agent_decisions if d.result == DecisionResult.APPROVAL_REQUIRED)
        blocked_actions = sum(1 for d in agent_decisions if d.result == DecisionResult.BLOCK)
        tool_total = len(agent_decisions)
        tool_efficiency = round(allowed / tool_total, 3) if tool_total else 1.0

        estimated_cost = round(float(sum(c.amount_usd for c in agent_costs)), 4)
        retry_count = sum(1 for e in agent_events if e.type == "task.failed")

        contributions = sum(1 for e in agent_events if e.type in ("agent.reasoning", "agent.message"))
        memory_utilization = round(min(1.0, contributions / 2.0), 3)

        metrics = {
            "task_success_rate": task_success_rate,
            "completion_latency_ms": completion_latency_ms,
            "handoff_quality": handoff_quality,
            "reasoning_quality": reasoning_quality,
            "tool_efficiency": tool_efficiency,
            "approval_count": approval_count,
            "blocked_actions": blocked_actions,
            "estimated_cost": estimated_cost,
            "retry_count": retry_count,
            "memory_utilization": memory_utilization,
        }

        base = (0.30 * task_success_rate + 0.20 * reasoning_quality + 0.15 * tool_efficiency
                + 0.15 * handoff_quality + 0.10 * memory_utilization + 0.10)
        score = _clamp(base * 100 - 5 * blocked_actions - 4 * retry_count - 2 * approval_count)

        weaknesses = self._detect(agent, metrics, mission, tasks, events)
        return AgentEvaluation(metrics=metrics, score=score, weaknesses=weaknesses)

    def _detect(self, agent: Agent, m: dict, mission: Mission, tasks: list[MissionTask],
                events: list[Event]) -> list[dict]:
        w: list[dict] = []

        def add(code: str, label: str, detail: str, metric: str | None = None) -> None:
            w.append({"code": code, "label": label, "detail": detail, "metric": metric})

        if m["retry_count"] >= 2:
            add("too_many_retries", "Too many retries",
                f"{m['retry_count']} failed attempts this mission.", "retry_count")
        if agent.key == "pm" and len(tasks) < 3:
            add("poor_task_decomposition", "Poor task decomposition",
                f"Only {len(tasks)} tasks created for the mission.", "tasks")
        if agent.key == "developer" and m["approval_count"] >= 1:
            add("high_deployment_approval_rate", "High deployment approval rate",
                "Deployment required human approval; planning could reduce approval risk.", "approval_count")
        if agent.key == "qa" and sum(1 for e in events if e.type == "qa.issue_found") >= 2:
            add("repeated_qa_failures", "Repeated QA failures",
                "Multiple QA issue rounds detected.", "issues")
        if m["blocked_actions"] >= 1:
            add("high_security_violations", "High security violations",
                "Requested an action blocked by governance (e.g. unauthorized data export).", "blocked_actions")
        if float(m["estimated_cost"]) > float(mission.budget_usd) / 5.0:
            add("budget_overrun", "Budget overrun",
                f"Spent ${m['estimated_cost']:.2f}, above the fair per-agent share.", "estimated_cost")
        if m["reasoning_quality"] < 0.7:
            add("low_reasoning_confidence", "Low reasoning confidence",
                f"Average confidence {m['reasoning_quality']:.2f} is below threshold.", "reasoning_quality")
        return w
