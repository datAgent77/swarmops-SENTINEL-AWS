"""Sentinel web-UI routes — the SAME authority the Alexa+ MCP server uses.

Both surfaces call the one OfficerService, so a human approving in the web console
and a human approving through Alexa+ are governed identically.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.sentinel.officer.service import DEMO_INCIDENT_ID, officer

router = APIRouter(prefix="/api/sentinel", tags=["sentinel"])


class ProposeBody(BaseModel):
    action_type: str
    actor_id: str = "owner-alex"
    incident_id: str = DEMO_INCIDENT_ID
    # Stable client id so retries of the SAME request never duplicate execution.
    action_request_id: str | None = None


class ResolveBody(BaseModel):
    approval_id: str
    actor_id: str
    incident_id: str = DEMO_INCIDENT_ID


class ResolveIncidentBody(BaseModel):
    actor_id: str = "officer-sam"
    incident_id: str = DEMO_INCIDENT_ID


@router.get("/incident")
async def incident(incident_id: str = DEMO_INCIDENT_ID) -> dict:
    return officer.get_incident(incident_id)


@router.get("/explain")
async def explain(incident_id: str = DEMO_INCIDENT_ID) -> dict:
    return officer.explain(incident_id)


@router.get("/actions")
async def actions(incident_id: str = DEMO_INCIDENT_ID) -> dict:
    return {"incident_id": incident_id, "actions": officer.allowed_actions(incident_id)}


@router.get("/timeline")
async def timeline(incident_id: str = DEMO_INCIDENT_ID) -> dict:
    return {"incident_id": incident_id, "timeline": officer.timeline(incident_id)}


@router.post("/propose")
async def propose(body: ProposeBody) -> dict:
    return officer.propose(body.incident_id, body.action_type, body.actor_id,
                           action_request_id=body.action_request_id)


@router.post("/resolve")
async def resolve(body: ResolveIncidentBody) -> dict:
    return officer.resolve(body.incident_id, body.actor_id)


@router.get("/winner-proof")
async def winner_proof() -> dict:
    """Prove exactly-once: warning is approved and executes, then the exact same
    request is replayed and DUPLICATE EXECUTION is PREVENTED (one execution only)."""
    return officer.winner_proof()


@router.post("/approve")
async def approve(body: ResolveBody) -> dict:
    return officer.approve(body.incident_id, body.approval_id, body.actor_id)


@router.post("/reject")
async def reject(body: ResolveBody) -> dict:
    return officer.reject(body.incident_id, body.approval_id, body.actor_id)
