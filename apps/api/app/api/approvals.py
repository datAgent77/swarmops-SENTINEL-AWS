"""Approval routes. DB work runs in a threadpool; resume signaling on the loop."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.db.session import SessionLocal
from app.domain.schemas import MissionSnapshot
from app.orchestration.coordinator import coordinator
from app.services.approval_service import approval_service
from app.services.mission_service import mission_service

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _snapshot(mission_id: uuid.UUID) -> MissionSnapshot:
    with SessionLocal() as session:
        return mission_service.get_snapshot(session, mission_id)


async def _decide(approval_id: uuid.UUID, outcome: str) -> MissionSnapshot:
    result = await run_in_threadpool(approval_service.resolve_in_db, approval_id, outcome)
    mission_id = result["mission_id"]
    # Wake SSE subscribers and resume the paused orchestrator (on the event loop).
    coordinator.publish(str(mission_id), result["seq"])
    coordinator.signal_decision(str(approval_id), outcome)
    return await run_in_threadpool(_snapshot, mission_id)


@router.post("/{approval_id}/approve", response_model=MissionSnapshot)
async def approve(approval_id: uuid.UUID) -> MissionSnapshot:
    return await _decide(approval_id, "approved")


@router.post("/{approval_id}/reject", response_model=MissionSnapshot)
async def reject(approval_id: uuid.UUID) -> MissionSnapshot:
    return await _decide(approval_id, "rejected")
