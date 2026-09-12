"""Sentinel web-UI routes — the SAME authority the Alexa+ MCP server uses.

Both surfaces call the one OfficerService, so a human approving in the web console
and a human approving through Alexa+ are governed identically.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.mcp.server import PROTOCOL_VERSION, TOOLS
from app.sentinel.officer.service import DEMO_INCIDENT_ID, officer
from app.sentinel.perception.factory import bedrock_configured, build_perception_provider
from app.sentinel.ring.factory import get_ingest_service, get_simulator, reset_ingest_service

router = APIRouter(prefix="/api/sentinel", tags=["sentinel"])

# Canonical scene times for the deterministic guided demo (a scripted reproduction
# of a real 23:42 entrance incident). The Ring events themselves are ingested for real.
_SCENE_TIMES = ["23:42", "23:44", "23:47"]
_SCENE_LABELS = ["Human motion detected", "Second human motion event",
                 "Repeated entrance activity detected"]


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


@router.get("/status")
async def status() -> dict:
    """On-duty status + provider indicators, each reflecting real backend state."""
    settings = get_settings()
    ring = get_ingest_service().info()
    perception = build_perception_provider(settings)
    return {
        "on_duty": True,
        "location": "SaitALCorp Office",
        "status": "ENTRANCE MONITORED",
        "providers": {
            "ring": {"status": ring.status.value, "detail": ring.detail},
            "bedrock": {"status": "CONNECTED" if bedrock_configured(settings) else "DEMO_MODE",
                        "detail": f"perception via {perception.name}"},
            "swarmops": {"status": "ACTIVE", "detail": "deterministic governance"},
            "alexa_mcp": {"status": "READY", "detail": f"MCP {PROTOCOL_VERSION}",
                          "tools": len(TOOLS)},
        },
    }


@router.post("/demo/reset")
async def demo_reset() -> dict:
    """Reset ONLY demo state (incidents, execution engine, Ring intake)."""
    officer.reset_demo()
    reset_ingest_service()
    return {"ok": True}


@router.post("/demo/start")
async def demo_start() -> dict:
    """Run the guided demo against real backend engines: Ring intake → incident →
    perception → deterministic risk → AI recommends GRANT → SwarmOps DENY → warning
    (human approval required). Approval, execution, and the duplicate attempt are
    driven by the UI via /approve and /propose so the human stays in the loop."""
    settings = get_settings()
    reset_ingest_service()
    simulator = get_simulator(settings)
    ingest = get_ingest_service()

    # 1-4) Real Ring events enter the backend.
    ring_events: list[dict] = []
    for i, event_type in enumerate(("MOTION", "MOTION", "PACKAGE")):
        raw, sig = simulator.build_event(event_type, "ring-front-door")
        result = ingest.ingest_webhook(raw, sig)
        ev = result.event
        ring_events.append({
            "t": _SCENE_TIMES[i], "label": _SCENE_LABELS[i],
            "provider_event_type": ev.provider_event_type if ev else None,
            "event_id": ev.event_id if ev else None,
            "signature_verified": ev.signature_verified if ev else False,
        })

    # 5-10) Incident, perception, deterministic risk, GRANT→DENY, warning→approval.
    incident_id = officer.create_demo_incident()
    grant = officer.propose(incident_id, "GRANT_TEMPORARY_ACCESS", "owner-alex",
                            action_request_id="grant-1")
    warning = officer.propose(incident_id, "SEND_WARNING", "owner-alex",
                              action_request_id="warn-1")
    return {
        "incident_id": incident_id,
        "incident": officer.get_incident(incident_id),
        "explanation": officer.explain(incident_id),
        "ring_events": ring_events,
        "centerpiece": {
            "ai_recommendation": "GRANT_TEMPORARY_ACCESS",
            "decision": grant["decision"],
            "reason_codes": grant["reason_codes"],
        },
        "second_action": {
            "ai_recommendation": "SEND_WARNING",
            "decision": warning["decision"],
            "approval_id": warning.get("approval_id"),
            "action_request_id": "warn-1",
        },
        "timeline": officer.timeline(incident_id),
    }


@router.post("/approve")
async def approve(body: ResolveBody) -> dict:
    return officer.approve(body.incident_id, body.approval_id, body.actor_id)


@router.post("/reject")
async def reject(body: ResolveBody) -> dict:
    return officer.reject(body.incident_id, body.approval_id, body.actor_id)
