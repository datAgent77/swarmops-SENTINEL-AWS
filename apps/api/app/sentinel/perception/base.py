"""Perception provider contract, inputs, telemetry, and result types."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.sentinel.models import SecurityObservation


class PerceptionStatus(str, Enum):
    OK = "OK"            # a valid, schema-conformant observation was produced
    UNKNOWN = "UNKNOWN"  # safe fallback: any failure mode. Never implies access.


class PerceptionInput(BaseModel):
    """Everything the perceiver may see. All scene text is UNTRUSTED data."""

    event_metadata: dict[str, Any] = Field(default_factory=dict)   # normalized Ring event fields
    snapshot_reference: str | None = None                         # opaque handle, not a URL
    image_bytes: bytes | None = None                              # optional frame for vision
    image_media_type: str = "image/jpeg"
    scene_text: str | None = None                                # untrusted OCR / sign text
    incident_history: list[str] = Field(default_factory=list)     # short prior summaries
    environment: dict[str, Any] = Field(default_factory=dict)     # e.g. {"is_night": true}


class PerceptionTelemetry(BaseModel):
    """Operational metadata only — never chain-of-thought."""

    provider: str
    model: str
    request_id: str
    latency_ms: int
    confidence: float
    status: PerceptionStatus


class PerceptionResult(BaseModel):
    observation: SecurityObservation
    status: PerceptionStatus
    telemetry: PerceptionTelemetry
    low_confidence: bool = False

    @property
    def needs_human_review(self) -> bool:
        """Low trust → escalate to a human (e.g. REQUEST_LIVE_REVIEW). This is a
        signal, never an authorization."""
        return self.status is PerceptionStatus.UNKNOWN or self.low_confidence


@runtime_checkable
class SecurityPerceptionProvider(Protocol):
    name: str

    def perceive(self, perception_input: PerceptionInput) -> PerceptionResult: ...


def unknown_observation(summary: str = "Perception unavailable.") -> SecurityObservation:
    """The safe fallback: nothing asserted, zero confidence, explicit UNKNOWN code."""
    return SecurityObservation(
        confidence=0.0, observation_codes=["NO_RELEVANT_ACTIVITY"], summary=summary
    )
