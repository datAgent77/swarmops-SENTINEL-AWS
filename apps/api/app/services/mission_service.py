"""Mission business logic. Route handlers stay thin and call into here."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import session_scope
from app.domain.enums import AgentStatus, TaskStatus
from app.domain.errors import NotFoundError
from app.domain.schemas import (
    AgentRead,
    ApprovalRead,
    DashboardRead,
    MissionMetrics,
    MissionRead,
    MissionSnapshot,
    OrganizationRead,
    TaskRead,
)
from app.governance.engine import GovernanceEngine
from app.orchestration.workflow import MissionOrchestrator
from app.repositories import (
    AgentRepository,
    ApprovalRepository,
    CostRepository,
    EventRepository,
    MissionRepository,
    OrganizationRepository,
    TaskRepository,
)

_orchestrator = MissionOrchestrator()
_governance = GovernanceEngine()


class MissionService:
    # --- creation / start --------------------------------------------------
    def create_mission(self, session: Session, objective: str, budget_usd: float) -> MissionRead:
        org = OrganizationRepository(session).get_default()
        if org is None:
            raise NotFoundError("No organization is seeded. Run the seed first.")
        mission = MissionRepository(session).create(org.id, objective, Decimal(str(budget_usd)))
        session.flush()
        return MissionRead.model_validate(mission)

    def start_mission(self, mission_id: uuid.UUID) -> asyncio.Task:
        """Kick off the orchestrator as a background task (non-blocking)."""
        return asyncio.create_task(_orchestrator.run(mission_id))

    # --- reads -------------------------------------------------------------
    def get_dashboard(self, session: Session) -> DashboardRead:
        org = OrganizationRepository(session).get_default()
        agents = AgentRepository(session).list_for_org(org.id) if org else []
        missions = MissionRepository(session).list()
        return DashboardRead(
            organization=OrganizationRead.model_validate(org) if org else None,
            agents=[AgentRead.model_validate(a) for a in agents],
            missions=[MissionRead.model_validate(m) for m in missions],
            sponsors=get_settings().active_sponsors(),
        )

    def get_snapshot(self, session: Session, mission_id: uuid.UUID) -> MissionSnapshot:
        mission = MissionRepository(session).get(mission_id)
        if mission is None:
            raise NotFoundError("Mission not found", {"mission_id": str(mission_id)})
        agents = AgentRepository(session).list_for_org(mission.organization_id)
        tasks = TaskRepository(session).list_for_mission(mission_id)
        events = EventRepository(session).list_for_mission(mission_id)
        pending = ApprovalRepository(session).get_pending_for_mission(mission_id)
        total_cost = CostRepository(session).total_for_mission(mission_id)
        reasoning_events = [e for e in events if e.type == "agent.reasoning"]
        metrics = MissionMetrics(
            events=len(events),
            blocked=sum(1 for e in events if e.type == "governance.blocked"),
            approvals=sum(1 for e in events if e.type == "approval.requested"),
            tasks_total=len(tasks),
            tasks_done=sum(1 for t in tasks if t.status == TaskStatus.DONE),
            total_cost_usd=total_cost,
            budget_usd=mission.budget_usd,
            input_tokens=sum(int(e.payload.get("input_tokens", 0)) for e in reasoning_events),
            output_tokens=sum(int(e.payload.get("output_tokens", 0)) for e in reasoning_events),
            llm_calls=len(reasoning_events),
        )
        return MissionSnapshot(
            mission=MissionRead.model_validate(mission),
            agents=[AgentRead.model_validate(a) for a in agents],
            tasks=[TaskRead.model_validate(t) for t in tasks],
            pending_approval=ApprovalRead.model_validate(pending) if pending else None,
            metrics=metrics,
        )

    def list_events(self, session: Session, mission_id: uuid.UUID):
        if MissionRepository(session).get(mission_id) is None:
            raise NotFoundError("Mission not found", {"mission_id": str(mission_id)})
        return EventRepository(session).list_for_mission(mission_id)

    # --- Scenario E — repeated failure quarantine --------------------------
    def record_task_failure(self, mission_id: uuid.UUID, agent_key: str) -> dict:
        """Record a failed attempt; quarantine the agent at the deterministic threshold."""
        with session_scope() as session:
            mission = MissionRepository(session).get(mission_id)
            if mission is None:
                raise NotFoundError("Mission not found", {"mission_id": str(mission_id)})
            agents = AgentRepository(session)
            events = EventRepository(session)
            agent = agents.get_by_key(mission.organization_id, agent_key)
            if agent is None:
                raise NotFoundError("Agent not found", {"agent_key": agent_key})
            count = agents.increment_failure(agent)
            if _governance.is_quarantined(count):
                agents.set_status(agent, AgentStatus.QUARANTINED)
                events.append(mission_id, "agent.quarantined", agent_key,
                              f"{agent.name} quarantined after {count} failed attempts. "
                              "Automatic continuation by this agent is prevented.",
                              {"failure_count": count, "policy_id": "agent.repeated_failure.quarantine"})
                return {"failure_count": count, "quarantined": True}
            events.append(mission_id, "task.failed", agent_key,
                          f"{agent.name} failed the task (attempt {count}).",
                          {"failure_count": count})
            return {"failure_count": count, "quarantined": False}


mission_service = MissionService()
