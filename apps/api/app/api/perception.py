"""Perception routes — run Bedrock (or Mock) perception on a scene.

Returns AI perception ONLY: a structured ``SecurityObservation`` plus telemetry.
It carries no authority. The security DECISION is made elsewhere by deterministic
governance; this endpoint can never grant, deny, or execute anything.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.sentinel.perception.base import PerceptionInput
from app.sentinel.perception.factory import bedrock_configured, build_perception_provider

router = APIRouter(prefix="/api/perception", tags=["perception"])


class ObserveRequest(BaseModel):
    event_metadata: dict = Field(default_factory=dict)   # e.g. {"motion_type": "human"}
    scene_text: str | None = None                        # untrusted OCR / sign text
    environment: dict = Field(default_factory=dict)      # e.g. {"is_night": true}
    incident_history: list[str] = Field(default_factory=list)


@router.get("/status")
async def perception_status() -> dict:
    settings = get_settings()
    provider = build_perception_provider(settings)
    return {
        "provider": provider.name,
        "configured": bedrock_configured(settings),
        "model": settings.bedrock_model_id or "(mock)",
    }


@router.post("/observe")
async def observe(body: ObserveRequest) -> dict:
    provider = build_perception_provider()
    perception_input = PerceptionInput(
        event_metadata=body.event_metadata,
        scene_text=body.scene_text,
        environment=body.environment,
        incident_history=body.incident_history,
    )
    result = await run_in_threadpool(provider.perceive, perception_input)
    obs = result.observation
    return {
        "status": result.status.value,
        "needs_human_review": result.needs_human_review,
        "low_confidence": result.low_confidence,
        # AI perception only — note the deliberate absence of any authority field.
        "observation": obs.model_dump(),
        "telemetry": result.telemetry.model_dump(),
    }
