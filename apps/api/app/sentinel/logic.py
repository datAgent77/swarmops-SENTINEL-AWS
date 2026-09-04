"""Deterministic domain helpers for Sentinel.

Pure functions only — no I/O, no randomness, no wall-clock inside the scoring
(``now`` is passed in). These produce the deterministic *inputs* the governance
layer (P02) will decide on. The final access policy is intentionally NOT decided
here: this phase only proves the domain can represent a deterministic-DENY state.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, computed_field

from app.sentinel.enums import RiskLevel
from app.sentinel.models import (
    BuildingContext,
    RiskAssessment,
    SecurityEvent,
    SecurityObservation,
)

# Events at one location within this gap belong to the same incident.
CORRELATION_WINDOW_SECONDS: int = 300  # 5 minutes


def correlate_events(
    events: list[SecurityEvent], window_seconds: int = CORRELATION_WINDOW_SECONDS
) -> list[list[SecurityEvent]]:
    """Group events into incident-sized clusters.

    Events at the same location whose gap to the previous event is within
    ``window_seconds`` join the same cluster. Different locations never merge.
    Deterministic: input order does not matter (events are sorted by time).
    """
    groups: list[list[SecurityEvent]] = []
    by_location: dict[str, list[SecurityEvent]] = {}
    for event in events:
        by_location.setdefault(event.location_id, []).append(event)

    for location_events in by_location.values():
        ordered = sorted(location_events, key=lambda e: e.occurred_at)
        current: list[SecurityEvent] = []
        last_at: datetime | None = None
        for event in ordered:
            if last_at is not None and (event.occurred_at - last_at).total_seconds() > window_seconds:
                groups.append(current)
                current = []
            current.append(event)
            last_at = event.occurred_at
        if current:
            groups.append(current)
    return groups


# --- deterministic risk -------------------------------------------------------

# (factor code, points). Only triggered factors contribute; total capped at 100.
_LOW_VISIBILITY = frozenset({"low", "dark", "obstructed"})


def compute_risk(
    observation: SecurityObservation, context: BuildingContext, now: datetime
) -> RiskAssessment:
    """Recomputable risk from perception + context. Same inputs → same output."""
    factor_scores: dict[str, int] = {}

    if observation.person_present and not context.building_open:
        factor_scores["person_at_closed_building"] = 40
    if observation.prolonged_presence:
        factor_scores["prolonged_presence"] = 20
    if observation.repeated_activity:
        factor_scores["repeated_activity"] = 20
    if not context.building_open:
        factor_scores["outside_business_hours"] = 15
    if observation.person_present and not _has_verified_visitor(context, now):
        factor_scores["no_expected_visitor"] = 10
    if observation.visibility in _LOW_VISIBILITY:
        factor_scores["low_visibility"] = 5

    score = min(100, sum(factor_scores.values()))
    return RiskAssessment(
        risk_score=score,
        risk_level=_level_for(score),
        risk_factors=sorted(factor_scores),
        factor_scores=factor_scores,
        policy_context=access_preconditions(context, now).model_dump(),
    )


def _level_for(score: int) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 50:
        return RiskLevel.HIGH
    if score >= 25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


# --- deterministic access preconditions (inputs, not the final policy) ---------

class AccessPreconditions(BaseModel):
    """The four deterministic facts a GRANT_TEMPORARY_ACCESS policy will need.

    When ``all_satisfied`` is False the domain state is capable of a deterministic
    DENY. The mapping from these facts to a decision lives in the governance layer
    (P02) — not here.
    """

    within_business_hours: bool
    verified_visitor: bool
    approved_access_request: bool
    valid_credential: bool

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_satisfied(self) -> bool:
        return (
            self.within_business_hours
            and self.verified_visitor
            and self.approved_access_request
            and self.valid_credential
        )

    def failing_reason_codes(self) -> list[str]:
        codes: list[str] = []
        if not self.within_business_hours:
            codes.append("OUTSIDE_BUSINESS_HOURS")
        if not self.verified_visitor:
            codes.append("NO_VERIFIED_VISITOR")
        if not self.approved_access_request:
            codes.append("NO_APPROVED_ACCESS_REQUEST")
        if not self.valid_credential:
            codes.append("NO_VALID_CREDENTIAL")
        return codes


def _has_verified_visitor(context: BuildingContext, now: datetime) -> bool:
    return any(v.is_valid_at(now) for v in context.expected_visitors)


def access_preconditions(context: BuildingContext, now: datetime) -> AccessPreconditions:
    return AccessPreconditions(
        within_business_hours=context.building_open,
        verified_visitor=_has_verified_visitor(context, now),
        approved_access_request=any(a.is_active_at(now) for a in context.active_access_requests),
        valid_credential=context.credential_state.presented and context.credential_state.valid,
    )
