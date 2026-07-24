"""Mission routes. Handlers are thin; logic lives in MissionService."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.schemas import (
    DashboardRead,
    EventRead,
    MissionCreate,
    MissionRead,
    MissionSnapshot,
)
from app.evolution.schemas import MissionSummary
from app.evolution.service import evolution_service
from app.services.mission_service import mission_service

router = APIRouter(prefix="/api", tags=["missions"])


@router.get("/dashboard", response_model=DashboardRead)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardRead:
    return mission_service.get_dashboard(db)


@router.post("/missions", response_model=MissionRead, status_code=201)
async def create_mission(payload: MissionCreate, db: Session = Depends(get_db)) -> MissionRead:
    mission = mission_service.create_mission(db, payload.objective, payload.budget_usd)
    db.commit()  # commit before the orchestrator (separate session) reads the mission
    mission_service.start_mission(mission.id)
    return mission


@router.get("/missions", response_model=list[MissionRead])
def list_missions(db: Session = Depends(get_db)) -> list[MissionRead]:
    return mission_service.get_dashboard(db).missions


@router.get("/missions/{mission_id}", response_model=MissionSnapshot)
def get_mission(mission_id: uuid.UUID, db: Session = Depends(get_db)) -> MissionSnapshot:
    return mission_service.get_snapshot(db, mission_id)


@router.get("/missions/{mission_id}/events", response_model=list[EventRead])
def list_events(mission_id: uuid.UUID, db: Session = Depends(get_db)) -> list[EventRead]:
    return [EventRead.model_validate(e) for e in mission_service.list_events(db, mission_id)]


@router.get("/missions/{mission_id}/summary", response_model=MissionSummary)
def mission_summary(mission_id: uuid.UUID, db: Session = Depends(get_db)) -> MissionSummary:
    return evolution_service.get_mission_summary(db, mission_id)


@router.get("/missions/{mission_id}/report")
def mission_report(mission_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """The mission's Markdown report (agent output) + the cited.md URL if published."""
    from app.domain.errors import NotFoundError
    from app.publishing.report import build_mission_report

    try:
        title, markdown = build_mission_report(db, mission_id)
    except ValueError as exc:
        raise NotFoundError("Mission not found", {"mission_id": str(mission_id)}) from exc
    url = None
    for e in mission_service.list_events(db, mission_id):
        if e.type == "mission.published":
            url = e.payload.get("url")
    return {"title": title, "markdown": markdown, "url": url}
