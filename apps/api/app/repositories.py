"""Repository classes — the only place that touches the database.

Services and the orchestrator depend on these; they never issue raw SQL or hold
ORM query logic themselves. Each repository is constructed with a Session and
owns access to one aggregate.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import (
    Agent,
    AgentVersion,
    Approval,
    CostRecord,
    Event,
    GovernanceDecision,
    Mission,
    MissionTask,
    Organization,
    PerformanceReport,
    Policy,
)
from app.domain.enums import (
    AgentStatus,
    ApprovalStatus,
    DecisionResult,
    MissionStatus,
    TaskStatus,
    VersionStatus,
)


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_default(self) -> Organization | None:
        return self.session.scalars(select(Organization).order_by(Organization.created_at)).first()

    def create(self, name: str) -> Organization:
        org = Organization(name=name)
        self.session.add(org)
        self.session.flush()
        return org


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_org(self, org_id: uuid.UUID) -> list[Agent]:
        return list(
            self.session.scalars(
                select(Agent).where(Agent.organization_id == org_id).order_by(Agent.created_at)
            )
        )

    def get_by_key(self, org_id: uuid.UUID, key: str) -> Agent | None:
        return self.session.scalars(
            select(Agent).where(Agent.organization_id == org_id, Agent.key == key)
        ).first()

    def create(self, org_id: uuid.UUID, key: str, name: str, role: str, team: str,
               allowed_tools: list[str], budget_limit_usd: Decimal) -> Agent:
        agent = Agent(organization_id=org_id, key=key, name=name, role=role, team=team,
                      allowed_tools=allowed_tools, budget_limit_usd=budget_limit_usd)
        self.session.add(agent)
        self.session.flush()
        return agent

    def set_status(self, agent: Agent, status: AgentStatus) -> None:
        agent.status = status
        self.session.flush()

    def increment_failure(self, agent: Agent) -> int:
        agent.failure_count += 1
        self.session.flush()
        return agent.failure_count


class PolicyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, org_id: uuid.UUID, policy_id: str, description: str,
               default_result: DecisionResult, risk_score: int) -> Policy:
        existing = self.session.scalars(
            select(Policy).where(Policy.organization_id == org_id, Policy.policy_id == policy_id)
        ).first()
        if existing:
            existing.description = description
            existing.default_result = default_result
            existing.risk_score = risk_score
            self.session.flush()
            return existing
        policy = Policy(organization_id=org_id, policy_id=policy_id, description=description,
                        default_result=default_result, risk_score=risk_score)
        self.session.add(policy)
        self.session.flush()
        return policy

    def list_for_org(self, org_id: uuid.UUID) -> list[Policy]:
        return list(self.session.scalars(select(Policy).where(Policy.organization_id == org_id)))


class MissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, org_id: uuid.UUID, objective: str, budget_usd: Decimal) -> Mission:
        mission = Mission(organization_id=org_id, objective=objective, budget_usd=budget_usd)
        self.session.add(mission)
        self.session.flush()
        return mission

    def get(self, mission_id: uuid.UUID) -> Mission | None:
        return self.session.get(Mission, mission_id)

    def list(self) -> list[Mission]:
        return list(self.session.scalars(select(Mission).order_by(Mission.created_at.desc())))

    def set_status(self, mission: Mission, status: MissionStatus) -> None:
        mission.status = status
        if status is MissionStatus.COMPLETED:
            mission.completed_at = utcnow()
        self.session.flush()


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, mission_id: uuid.UUID, title: str, agent_id: uuid.UUID | None = None,
               status: TaskStatus = TaskStatus.PENDING) -> MissionTask:
        task = MissionTask(mission_id=mission_id, title=title, agent_id=agent_id, status=status)
        self.session.add(task)
        self.session.flush()
        return task

    def list_for_mission(self, mission_id: uuid.UUID) -> list[MissionTask]:
        return list(
            self.session.scalars(
                select(MissionTask).where(MissionTask.mission_id == mission_id).order_by(MissionTask.created_at)
            )
        )

    def set_status(self, task: MissionTask, status: TaskStatus) -> None:
        task.status = status
        self.session.flush()

    def increment_attempts(self, task: MissionTask) -> int:
        task.attempts += 1
        self.session.flush()
        return task.attempts


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, mission_id: uuid.UUID, type: str, actor_id: str, message: str,
               payload: dict | None = None) -> Event:
        event = Event(mission_id=mission_id, type=type, actor_id=actor_id, message=message,
                      payload=payload or {})
        self.session.add(event)
        self.session.flush()  # populates seq + id
        self.session.refresh(event)
        return event

    def list_for_mission(self, mission_id: uuid.UUID, after_seq: int | None = None) -> list[Event]:
        stmt = select(Event).where(Event.mission_id == mission_id)
        if after_seq is not None:
            stmt = stmt.where(Event.seq > after_seq)
        return list(self.session.scalars(stmt.order_by(Event.seq)))


class GovernanceDecisionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, mission_id: uuid.UUID, tool: str, environment: str, result: DecisionResult,
               risk_score: int, reason: str, policy_id: str, resource: str | None = None,
               agent_id: uuid.UUID | None = None) -> GovernanceDecision:
        decision = GovernanceDecision(mission_id=mission_id, tool=tool, environment=environment,
                                      result=result, risk_score=risk_score, reason=reason,
                                      policy_id=policy_id, resource=resource, agent_id=agent_id)
        self.session.add(decision)
        self.session.flush()
        return decision


class ApprovalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, mission_id: uuid.UUID, tool: str, reason: str, policy_id: str, risk_score: int,
               resource: str | None = None, agent_id: uuid.UUID | None = None) -> Approval:
        approval = Approval(mission_id=mission_id, tool=tool, reason=reason, policy_id=policy_id,
                            risk_score=risk_score, resource=resource, agent_id=agent_id)
        self.session.add(approval)
        self.session.flush()
        return approval

    def get(self, approval_id: uuid.UUID) -> Approval | None:
        return self.session.get(Approval, approval_id)

    def get_pending_for_mission(self, mission_id: uuid.UUID) -> Approval | None:
        return self.session.scalars(
            select(Approval).where(
                Approval.mission_id == mission_id, Approval.status == ApprovalStatus.PENDING
            ).order_by(Approval.created_at.desc())
        ).first()

    def resolve(self, approval: Approval, status: ApprovalStatus, decided_at: datetime) -> None:
        approval.status = status
        approval.decided_at = decided_at
        self.session.flush()


class CostRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, mission_id: uuid.UUID, description: str, amount_usd: Decimal,
               agent_id: uuid.UUID | None = None) -> CostRecord:
        record = CostRecord(mission_id=mission_id, description=description, amount_usd=amount_usd,
                            agent_id=agent_id)
        self.session.add(record)
        self.session.flush()
        return record

    def total_for_mission(self, mission_id: uuid.UUID) -> Decimal:
        rows = self.session.scalars(select(CostRecord.amount_usd).where(CostRecord.mission_id == mission_id))
        return sum(rows, Decimal("0.00"))


class PerformanceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, mission_id: uuid.UUID, agent_id: uuid.UUID, agent_key: str,
               score: float, metrics: dict, weaknesses: list) -> PerformanceReport:
        report = PerformanceReport(mission_id=mission_id, agent_id=agent_id, agent_key=agent_key,
                                   score=score, metrics=metrics, weaknesses=weaknesses)
        self.session.add(report)
        self.session.flush()
        return report

    def list_for_mission(self, mission_id: uuid.UUID) -> list[PerformanceReport]:
        return list(self.session.scalars(
            select(PerformanceReport).where(PerformanceReport.mission_id == mission_id)
            .order_by(PerformanceReport.score.desc())
        ))

    def history_for_agent(self, agent_key: str) -> list[PerformanceReport]:
        return list(self.session.scalars(
            select(PerformanceReport).where(PerformanceReport.agent_key == agent_key)
            .order_by(PerformanceReport.created_at)
        ))

    def latest_for_agent(self, agent_key: str) -> PerformanceReport | None:
        return self.session.scalars(
            select(PerformanceReport).where(PerformanceReport.agent_key == agent_key)
            .order_by(PerformanceReport.created_at.desc())
        ).first()


class VersionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, agent_id: uuid.UUID, agent_key: str, version: str, parent_version: str | None,
               status: VersionStatus, risk_level, reason: str, improvements: list,
               changes: dict, performance_delta: dict) -> AgentVersion:
        row = AgentVersion(agent_id=agent_id, agent_key=agent_key, version=version,
                           parent_version=parent_version, status=status, risk_level=risk_level,
                           reason=reason, improvements=improvements, changes=changes,
                           performance_delta=performance_delta)
        self.session.add(row)
        self.session.flush()
        return row

    def get(self, version_id: uuid.UUID) -> AgentVersion | None:
        return self.session.get(AgentVersion, version_id)

    def list_for_agent(self, agent_key: str) -> list[AgentVersion]:
        return list(self.session.scalars(
            select(AgentVersion).where(AgentVersion.agent_key == agent_key)
            .order_by(AgentVersion.created_at)
        ))

    def active_for_agent(self, agent_key: str) -> AgentVersion | None:
        return self.session.scalars(
            select(AgentVersion).where(AgentVersion.agent_key == agent_key,
                                       AgentVersion.status == VersionStatus.ACTIVE)
            .order_by(AgentVersion.created_at.desc())
        ).first()

    def latest_for_agent(self, agent_key: str) -> AgentVersion | None:
        return self.session.scalars(
            select(AgentVersion).where(AgentVersion.agent_key == agent_key)
            .order_by(AgentVersion.created_at.desc())
        ).first()

    def set_status(self, version: AgentVersion, status: VersionStatus,
                   activated_at: datetime | None = None) -> None:
        version.status = status
        if activated_at is not None:
            version.activated_at = activated_at
        self.session.flush()
