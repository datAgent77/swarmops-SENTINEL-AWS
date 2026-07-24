"""Evolution routes (Sprint 4). Handlers are thin; logic lives in EvolutionService."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.evolution.schemas import (
    AgentVersionRead,
    EvolutionAgentCard,
    VersionComparison,
)
from app.evolution.service import evolution_service
from app.repositories import VersionRepository

router = APIRouter(prefix="/api/evolution", tags=["evolution"])


@router.get("/agents", response_model=list[EvolutionAgentCard])
def evolution_dashboard(db: Session = Depends(get_db)) -> list[EvolutionAgentCard]:
    return evolution_service.get_dashboard(db)


@router.get("/agents/{agent_key}/versions", response_model=list[AgentVersionRead])
def agent_versions(agent_key: str, db: Session = Depends(get_db)) -> list[AgentVersionRead]:
    return [AgentVersionRead.model_validate(v) for v in VersionRepository(db).list_for_agent(agent_key)]


@router.get("/versions/{version_id}/comparison", response_model=VersionComparison)
def version_comparison(version_id: uuid.UUID, db: Session = Depends(get_db)) -> VersionComparison:
    return evolution_service.get_comparison(db, version_id)


@router.post("/versions/{version_id}/approve", response_model=AgentVersionRead)
def approve_version(version_id: uuid.UUID) -> AgentVersionRead:
    return evolution_service.approve_version(version_id)


@router.post("/versions/{version_id}/reject", response_model=AgentVersionRead)
def reject_version(version_id: uuid.UUID) -> AgentVersionRead:
    return evolution_service.reject_version(version_id)


@router.post("/agents/{agent_key}/rollback/{version_id}", response_model=AgentVersionRead)
def rollback(agent_key: str, version_id: uuid.UUID) -> AgentVersionRead:
    return evolution_service.rollback(agent_key, version_id)
