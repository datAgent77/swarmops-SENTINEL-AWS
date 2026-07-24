"""SQLAlchemy ORM models — the persistent source of truth (PostgreSQL).

All primary keys are UUIDs; all timestamps are timezone-aware UTC. Money is
stored as Numeric. Event ordering uses a global identity ``seq`` so streams can
be replayed deterministically and reconnected via Last-Event-ID.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_column, utcnow, uuid_pk
from app.db.types import EnumString
from app.domain.enums import (
    AgentStatus,
    ApprovalStatus,
    DecisionResult,
    MissionStatus,
    RiskLevel,
    TaskStatus,
    VersionStatus,
)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created_column()

    agents: Mapped[list[Agent]] = relationship(back_populates="organization")


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_agent_org_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(50), nullable=False)  # stable slug e.g. "developer"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    team: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AgentStatus] = mapped_column(EnumString(AgentStatus), default=AgentStatus.IDLE, nullable=False)
    allowed_tools: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    budget_limit_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1.00"), nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = created_column()

    organization: Mapped[Organization] = relationship(back_populates="agents")


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("organization_id", "policy_id", name="uq_policy_org_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. deployment.production.human_approval
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_result: Mapped[DecisionResult] = mapped_column(EnumString(DecisionResult), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_column()


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    budget_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("5.00"), nullable=False)
    status: Mapped[MissionStatus] = mapped_column(
        EnumString(MissionStatus), default=MissionStatus.CREATED, nullable=False
    )
    created_at: Mapped[datetime] = created_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tasks: Mapped[list[MissionTask]] = relationship(back_populates="mission")


class MissionTask(Base):
    __tablename__ = "mission_tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id"), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(EnumString(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = created_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    mission: Mapped[Mission] = relationship(back_populates="tasks")


class Event(Base):
    """Append-only audit event. Never updated or deleted in normal execution."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Global monotonic sequence for stable ordering + Last-Event-ID reconnection.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True, index=True, nullable=False)
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(60), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = created_column()


class GovernanceDecision(Base):
    __tablename__ = "governance_decisions"

    id: Mapped[uuid.UUID] = uuid_pk()
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id"), index=True, nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(200), nullable=True)
    environment: Mapped[str] = mapped_column(String(30), nullable=False)
    result: Mapped[DecisionResult] = mapped_column(EnumString(DecisionResult), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_column()


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = uuid_pk()
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id"), index=True, nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        EnumString(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = created_column()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CostRecord(Base):
    __tablename__ = "cost_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id"), index=True, nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = created_column()


# --- Sprint 4: Self-Evolving Workforce (new tables; existing schema untouched) ---

class PerformanceReport(Base):
    """Per-agent evaluation produced after a mission completes. Append-only."""

    __tablename__ = "performance_reports"

    id: Mapped[uuid.UUID] = uuid_pk()
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id"), index=True, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), index=True, nullable=False)
    agent_key: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)  # 0..100
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    weaknesses: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = created_column()


class AgentVersion(Base):
    """An immutable version of an agent's *data* (prompts, planning, style, tool
    preferences) — never executable code. History is preserved; status flags
    which one is active. High-risk versions require approval before activation.
    """

    __tablename__ = "agent_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id"), index=True, nullable=False)
    agent_key: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)          # e.g. "1.2"
    parent_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[VersionStatus] = mapped_column(
        EnumString(VersionStatus), default=VersionStatus.PROPOSED, nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        EnumString(RiskLevel), default=RiskLevel.LOW, nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    improvements: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)   # structured suggestions
    changes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)        # stored (non-code) deltas
    performance_delta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = created_column()
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
