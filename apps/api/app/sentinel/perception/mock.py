"""Deterministic perception provider for tests and the no-key demo.

Derives a plausible observation from normalized Ring metadata (no network), and
can be steered to exercise failure modes and raw-output parsing. It describes
untrusted scene text but never acts on it.
"""

from __future__ import annotations

import uuid

from app.sentinel.models import SecurityObservation
from app.sentinel.perception.assemble import ok_result, unknown_result
from app.sentinel.perception.base import PerceptionInput, PerceptionResult
from app.sentinel.perception.parse import PerceptionSchemaError, parse_observation

MODEL = "mock-perception-1"


class MockSecurityPerceptionProvider:
    name = "mock"

    def __init__(
        self,
        *,
        observation: SecurityObservation | None = None,
        raw_output: str | None = None,
        fail: str | None = None,             # "timeout" | "unavailable" | None
        min_confidence: float = 0.5,
    ) -> None:
        self._observation = observation
        self._raw_output = raw_output
        self._fail = fail
        self._min_confidence = min_confidence

    def perceive(self, perception_input: PerceptionInput) -> PerceptionResult:
        rid = f"mock-{uuid.uuid4().hex[:12]}"
        if self._fail:
            return unknown_result(provider=self.name, model=MODEL, request_id=rid,
                                  latency_ms=0, reason=self._fail)

        if self._raw_output is not None:
            try:
                obs = parse_observation(self._raw_output)
            except PerceptionSchemaError as exc:
                return unknown_result(provider=self.name, model=MODEL, request_id=rid,
                                      latency_ms=1, reason=str(exc))
            return ok_result(obs, provider=self.name, model=MODEL, request_id=rid,
                             latency_ms=1, min_confidence=self._min_confidence)

        obs = self._observation or self._derive(perception_input)
        return ok_result(obs, provider=self.name, model=MODEL, request_id=rid,
                         latency_ms=1, min_confidence=self._min_confidence)

    def _derive(self, perception_input: PerceptionInput) -> SecurityObservation:
        meta = perception_input.event_metadata
        motion = str(meta.get("motion_type") or "").lower()
        person = motion == "human" or bool(meta.get("person_present"))
        package = motion == "package"
        vehicle = motion == "vehicle"
        is_night = bool(perception_input.environment.get("is_night"))

        codes: list[str] = []
        if person:
            codes.append("PERSON_PRESENT")
        if vehicle:
            codes.append("VEHICLE_PRESENT")
        if package:
            codes.append("PACKAGE_PRESENT")
            codes.append("DELIVERY_LIKELY")
        if is_night:
            codes.append("VISIBILITY_LOW")
        if not codes:
            codes.append("NO_RELEVANT_ACTIVITY")

        summary_bits = []
        if person:
            summary_bits.append("a person at the entrance")
        if package:
            summary_bits.append("a package")
        if vehicle:
            summary_bits.append("a vehicle")
        summary = "Observed " + (", ".join(summary_bits) if summary_bits else "no relevant activity")
        # Describe (never obey) any untrusted scene text.
        if perception_input.scene_text:
            summary += "; a sign is visible in the scene (content treated as untrusted)"

        return SecurityObservation(
            person_present=person, vehicle_present=vehicle, package_present=package,
            entrance_activity=person or package or vehicle,
            prolonged_presence=False, repeated_activity=False,
            visibility="dark" if is_night else "clear",
            confidence=0.9, observation_codes=codes, summary=summary + ".",
        )
