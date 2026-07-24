"""Pydantic request/response schemas for the API (snake_case throughout)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AgentStatus, ApprovalStatus, DecisionResult, MissionStatus, TaskStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- requests -----------------------------------------------------------------
class MissionCreate(BaseModel):
    objective: str = Field(min_length=5, max_length=500)
    budget_usd: float = Field(default=5.0, gt=0, le=100)


# --- responses ----------------------------------------------------------------
class AgentRead(ORMModel):
    id: uuid.UUID
    key: str
    name: str
    role: str
    team: str
    status: AgentStatus
    allowed_tools: list[str]
    budget_limit_usd: Decimal
    failure_count: int


class MissionRead(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    objective: str
    budget_usd: Decimal
    status: MissionStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TaskRead(ORMModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    agent_id: uuid.UUID | None
    title: str
    status: TaskStatus
    attempts: int


class EventRead(ORMModel):
    id: uuid.UUID
    seq: int
    mission_id: uuid.UUID
    type: str
    actor_id: str
    message: str
    payload: dict
    created_at: datetime


class ApprovalRead(ORMModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    agent_id: uuid.UUID | None
    tool: str
    resource: str | None
    reason: str
    policy_id: str
    risk_score: int
    status: ApprovalStatus
    created_at: datetime
    decided_at: datetime | None


class DecisionRead(ORMModel):
    id: uuid.UUID
    tool: str
    resource: str | None
    environment: str
    result: DecisionResult
    risk_score: int
    reason: str
    policy_id: str
    created_at: datetime


class MissionMetrics(BaseModel):
    events: int
    blocked: int
    approvals: int
    tasks_total: int
    tasks_done: int
    total_cost_usd: Decimal
    budget_usd: Decimal
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0


class MissionSnapshot(BaseModel):
    mission: MissionRead
    agents: list[AgentRead]
    tasks: list[TaskRead]
    pending_approval: ApprovalRead | None
    metrics: MissionMetrics


class OrganizationRead(ORMModel):
    id: uuid.UUID
    name: str


class DashboardRead(BaseModel):
    organization: OrganizationRead | None
    agents: list[AgentRead]
    missions: list[MissionRead]
    sponsors: list[str] = []  # configured sponsor integrations (band|senso|pioneer)
