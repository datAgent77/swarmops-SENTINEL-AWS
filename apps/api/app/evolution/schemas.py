"""Pydantic schemas for the self-evolving workforce (Sprint 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import RiskLevel, VersionStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Weakness(BaseModel):
    code: str
    label: str
    detail: str
    metric: str | None = None


class ImprovementSuggestion(BaseModel):
    weakness: str
    suggestion: str
    expected_impact: str
    risk: RiskLevel
    category: str
    changes: dict = {}


class PerformanceReportRead(ORMModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    agent_id: uuid.UUID
    agent_key: str
    score: float
    metrics: dict
    weaknesses: list
    created_at: datetime


class AgentVersionRead(ORMModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    agent_key: str
    version: str
    parent_version: str | None
    status: VersionStatus
    risk_level: RiskLevel
    reason: str
    improvements: list
    changes: dict
    performance_delta: dict
    created_at: datetime
    activated_at: datetime | None


class EvolutionAgentCard(BaseModel):
    agent_key: str
    name: str
    current_version: str
    performance_score: float
    improvement_score: float
    trend: str  # "up" | "down" | "flat"
    pending_version: AgentVersionRead | None = None


class MissionSummary(BaseModel):
    mission_id: uuid.UUID
    top_performer: str | None = None
    most_improved: str | None = None
    highest_cost_agent: str | None = None
    highest_risk_agent: str | None = None
    biggest_opportunity: str | None = None
    reports: list[PerformanceReportRead] = []


class VersionComparison(BaseModel):
    agent_key: str
    from_version: str
    to_version: str
    metrics: list[dict]  # [{label, before, after}]
