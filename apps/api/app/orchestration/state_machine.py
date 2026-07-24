"""Explicit mission state machine. Invalid transitions are rejected."""

from __future__ import annotations

from app.domain.enums import MissionStatus
from app.domain.errors import InvalidTransitionError

# Allowed forward transitions. Terminal states (completed, rejected, failed,
# blocked) have no outgoing edges.
ALLOWED: dict[MissionStatus, frozenset[MissionStatus]] = {
    MissionStatus.CREATED: frozenset({MissionStatus.PLANNING, MissionStatus.FAILED}),
    MissionStatus.PLANNING: frozenset({MissionStatus.ASSIGNED, MissionStatus.FAILED}),
    MissionStatus.ASSIGNED: frozenset({MissionStatus.RUNNING, MissionStatus.FAILED}),
    MissionStatus.RUNNING: frozenset(
        {MissionStatus.WAITING_APPROVAL, MissionStatus.VALIDATING, MissionStatus.BLOCKED, MissionStatus.FAILED}
    ),
    MissionStatus.WAITING_APPROVAL: frozenset(
        {MissionStatus.RUNNING, MissionStatus.REJECTED, MissionStatus.FAILED}
    ),
    MissionStatus.VALIDATING: frozenset(
        {MissionStatus.RUNNING, MissionStatus.COMPLETED, MissionStatus.FAILED}
    ),
    MissionStatus.COMPLETED: frozenset(),
    MissionStatus.REJECTED: frozenset(),
    MissionStatus.FAILED: frozenset(),
    MissionStatus.BLOCKED: frozenset(),
}


def can_transition(current: MissionStatus, target: MissionStatus) -> bool:
    return target in ALLOWED.get(current, frozenset())


def assert_transition(current: MissionStatus, target: MissionStatus) -> None:
    if not can_transition(current, target):
        raise InvalidTransitionError(
            f"Mission cannot move from '{current.value}' to '{target.value}'.",
            details={"from": current.value, "to": target.value},
        )
