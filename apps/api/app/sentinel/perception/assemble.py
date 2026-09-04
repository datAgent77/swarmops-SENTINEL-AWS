"""Assemble PerceptionResult objects with telemetry (no chain-of-thought)."""

from __future__ import annotations

from app.sentinel.models import SecurityObservation
from app.sentinel.perception.base import (
    PerceptionResult,
    PerceptionStatus,
    PerceptionTelemetry,
    unknown_observation,
)

DEFAULT_MIN_CONFIDENCE = 0.5


def ok_result(
    observation: SecurityObservation,
    *,
    provider: str,
    model: str,
    request_id: str,
    latency_ms: int,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> PerceptionResult:
    return PerceptionResult(
        observation=observation,
        status=PerceptionStatus.OK,
        low_confidence=observation.confidence < min_confidence,
        telemetry=PerceptionTelemetry(
            provider=provider, model=model, request_id=request_id,
            latency_ms=latency_ms, confidence=observation.confidence,
            status=PerceptionStatus.OK,
        ),
    )


def unknown_result(
    *, provider: str, model: str, request_id: str, latency_ms: int, reason: str
) -> PerceptionResult:
    """Safe fallback for EVERY failure mode. Never implies access."""
    obs = unknown_observation(f"Perception unavailable: {reason}.")
    return PerceptionResult(
        observation=obs,
        status=PerceptionStatus.UNKNOWN,
        low_confidence=True,
        telemetry=PerceptionTelemetry(
            provider=provider, model=model, request_id=request_id,
            latency_ms=latency_ms, confidence=0.0, status=PerceptionStatus.UNKNOWN,
        ),
    )
