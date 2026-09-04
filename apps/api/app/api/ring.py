"""Ring sensing routes — status, real webhook intake, and Playground simulation.

- ``GET /api/ring/status`` reports the true backend provider state (never a false
  green): CONNECTED / DEMO_MODE / NOT_CONFIGURED / ERROR.
- ``POST /api/ring/webhook`` accepts a real Ring event, verifies the
  ``X-Signature`` HMAC over the raw body, then normalizes → dedupes → correlates.
- ``POST /api/ring/simulate`` builds a documented, signed Ring event and feeds it
  through the identical pipeline — what a judge sees entering the backend at
  runtime without a physical device.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.config import get_settings
from app.sentinel.ring.factory import get_ingest_service, get_simulator
from app.sentinel.ring.ingest import IngestResult
from app.sentinel.ring.webhook import SIGNATURE_HEADER

router = APIRouter(prefix="/api/ring", tags=["ring"])


class SimulateRequest(BaseModel):
    event_type: str = "MOTION"        # MOTION | PACKAGE | VEHICLE | DOORBELL
    device_id: str = "ring-front-door"
    component_id: int | None = None


def _result_payload(result: IngestResult) -> dict:
    event = result.event
    incident = result.incident
    return {
        "accepted": result.accepted,
        "duplicate": result.duplicate,
        "reason": result.reason,
        "event": None if event is None else {
            "event_id": event.event_id,
            "provider": event.provider,
            "provider_event_type": event.provider_event_type,
            "type": event.type.value,
            "device_id": event.device_id,
            "component_id": event.component_id,
            "motion_type": event.motion_type,
            "location_id": event.location_id,
            "occurred_at": event.occurred_at.isoformat(),
            "signature_verified": event.signature_verified,
            "media_reference": event.media_reference,
            "raw_metadata_hash": event.raw_metadata_hash,
        },
        "incident": None if incident is None else {
            "incident_id": incident.incident_id,
            "status": incident.status.value,
            "severity": incident.severity.value,
            "event_count": len(incident.event_ids),
            "device_ids": incident.device_ids,
        },
        "audit": [a.action for a in result.audits],
    }


@router.get("/status")
async def ring_status() -> dict:
    info = get_ingest_service().info()
    return {"provider": info.provider, "status": info.status.value, "detail": info.detail}


@router.post("/webhook")
async def ring_webhook(request: Request, response: Response) -> dict:
    raw = await request.body()
    signature = request.headers.get(SIGNATURE_HEADER)
    result = get_ingest_service().ingest_webhook(raw, signature)
    if not result.accepted:
        # Forged/unsigned → 401; malformed → 400. Never process untrusted bodies.
        response.status_code = 401 if result.reason == "invalid_signature" else (
            200 if result.duplicate else 400
        )
    return _result_payload(result)


@router.post("/simulate")
async def ring_simulate(body: SimulateRequest) -> dict:
    settings = get_settings()
    simulator = get_simulator(settings)
    raw, signature = simulator.build_event(
        body.event_type, body.device_id, component_id=body.component_id
    )
    result = get_ingest_service().ingest_webhook(raw, signature)
    return _result_payload(result)
