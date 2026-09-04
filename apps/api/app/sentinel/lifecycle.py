"""Explicit incident lifecycle state machine.

Mirrors the base ``app.orchestration.state_machine`` pattern: a fixed transition
map, with any move not listed rejected. Terminal states (RESOLVED, DISMISSED)
have no outgoing edges. Reuses the base ``InvalidTransitionError`` so the API
error envelope is consistent across missions and incidents.

    OBSERVE → UNDERSTAND → ASSESS → DECIDE → ESCALATE → ACT → RECORD

realized as:

    DETECTED → OBSERVING → ASSESSING → (ESCALATED) → AWAITING_APPROVAL
             → ACTIONED → RESOLVED     (with DISMISSED reachable from any
                                        non-terminal state as a false alarm)
"""

from __future__ import annotations

from app.domain.errors import InvalidTransitionError
from app.sentinel.enums import IncidentStatus as S

ALLOWED: dict[S, frozenset[S]] = {
    S.DETECTED: frozenset({S.OBSERVING, S.DISMISSED}),
    S.OBSERVING: frozenset({S.ASSESSING, S.DISMISSED}),
    S.ASSESSING: frozenset(
        {S.ESCALATED, S.AWAITING_APPROVAL, S.ACTIONED, S.RESOLVED, S.DISMISSED}
    ),
    S.ESCALATED: frozenset({S.AWAITING_APPROVAL, S.ACTIONED, S.RESOLVED, S.DISMISSED}),
    S.AWAITING_APPROVAL: frozenset({S.ACTIONED, S.ESCALATED, S.RESOLVED, S.DISMISSED}),
    S.ACTIONED: frozenset({S.RESOLVED, S.AWAITING_APPROVAL, S.ESCALATED, S.DISMISSED}),
    S.RESOLVED: frozenset(),
    S.DISMISSED: frozenset(),
}


def can_transition(current: S, target: S) -> bool:
    return target in ALLOWED.get(current, frozenset())


def assert_transition(current: S, target: S) -> S:
    """Return ``target`` if the transition is allowed, else raise."""
    if not can_transition(current, target):
        raise InvalidTransitionError(
            f"Incident cannot move from '{current.value}' to '{target.value}'.",
            details={"from": current.value, "to": target.value},
        )
    return target
