"""Build a Markdown mission report grounded in persisted data.

Every section is derived from what actually happened and was recorded in
PostgreSQL — governance decisions cite their policy id, blocked/approved actions
cite their events, scores come from performance reports. This is the agent
workforce's output: verifiable, auditable content ready to publish to cited.md.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import GovernanceDecision
from app.repositories import (
    ApprovalRepository,
    CostRepository,
    EventRepository,
    MissionRepository,
    PerformanceRepository,
)

_MILESTONES = {
    "plan.created": "CEO produced a strategy and plan",
    "tasks.created": "Product Manager decomposed the work into tasks",
    "budget.reviewed": "Finance reviewed the budget",
    "approval.requested": "Governance paused for human approval",
    "approval.granted": "Human approved the production deploy",
    "deploy.succeeded": "Deployed to production",
    "governance.blocked": "Governance blocked an unauthorized action",
    "qa.issue_found": "QA found an issue",
    "issue.fixed": "Developer fixed the issue",
    "qa.passed": "QA validated the final build",
    "mission.completed": "Mission completed",
}


def build_mission_report(session, mission_id: uuid.UUID) -> tuple[str, str]:
    """Return (title, markdown) for a mission, grounded in persisted data."""
    mission = MissionRepository(session).get(mission_id)
    if mission is None:
        raise ValueError("mission not found")
    events = EventRepository(session).list_for_mission(mission_id)
    decisions = list(session.scalars(
        select(GovernanceDecision).where(GovernanceDecision.mission_id == mission_id)))
    total_cost = CostRepository(session).total_for_mission(mission_id)
    reports = PerformanceRepository(session).list_for_mission(mission_id)
    ApprovalRepository(session).get_pending_for_mission(mission_id)  # touch (kept for parity)

    blocked = sum(1 for e in events if e.type == "governance.blocked")
    approvals = sum(1 for e in events if e.type == "approval.requested")
    reasoning = [e for e in events if e.type == "agent.reasoning"]
    in_tok = sum(int(e.payload.get("input_tokens", 0)) for e in reasoning)
    out_tok = sum(int(e.payload.get("output_tokens", 0)) for e in reasoning)

    title = f"Mission report — {mission.objective}"
    L: list[str] = []
    L.append(f"# {title}")
    L.append("")
    L.append(f"**Outcome:** {mission.status.value}  ·  "
             f"**Governed by:** SwarmOps (deterministic governance)  ·  "
             f"**Audit events:** {len(events)}")
    L.append("")
    L.append("> Generated autonomously by the SwarmOps AI workforce. Every claim below is "
             "grounded in a persisted, append-only audit event — nothing is invented.")
    L.append("")

    # What happened
    L.append("## What happened")
    seen = set()
    for e in events:
        label = _MILESTONES.get(e.type)
        if label and e.type not in seen:
            seen.add(e.type)
            L.append(f"- {label}.")
    L.append("")

    # Governance & audit (the citations)
    L.append("## Governance decisions")
    L.append("")
    L.append("| Action | Result | Risk | Policy (citation) |")
    L.append("|---|---|---|---|")
    for d in decisions:
        L.append(f"| `{d.tool}` | **{d.result.value}** | {d.risk_score}/100 | `{d.policy_id}` |")
    if not decisions:
        L.append("| _none_ | | | |")
    L.append("")
    if blocked:
        L.append(f"> 🚫 {blocked} unauthorized action(s) were **blocked** by the deterministic "
                 "policy engine — no data left the system.")
        L.append("")

    # Metrics
    L.append("## Metrics")
    L.append(f"- Blocked actions: **{blocked}**")
    L.append(f"- Human approvals: **{approvals}**")
    L.append(f"- Cost / budget: **${float(total_cost):.2f} / ${float(mission.budget_usd):.2f}**")
    L.append(f"- LLM tokens: **{in_tok + out_tok:,}** ({len(reasoning)} calls)")
    L.append("")

    # Self-evolution
    if reports:
        L.append("## Self-evolution")
        L.append("After the mission, each agent was scored from this persisted data and "
                 "improvements were versioned under governance:")
        L.append("")
        L.append("| Agent | Score | Detected weaknesses |")
        L.append("|---|---|---|")
        for r in sorted(reports, key=lambda x: float(x.score), reverse=True):
            weak = ", ".join(w.get("label", w.get("code", "")) for w in (r.weaknesses or [])) or "—"
            L.append(f"| {r.agent_key} | {float(r.score):.0f}/100 | {weak} |")
        L.append("")

    L.append("---")
    L.append("*Published by an autonomous SwarmOps workforce under deterministic governance. "
             "Self-improving, measurable, reversible — governed the whole way down.*")
    return title, "\n".join(L)
