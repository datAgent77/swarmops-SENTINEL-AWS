"""State machine transition rules and Scenario E quarantine behavior."""

import uuid
from decimal import Decimal

import pytest

from app.db.session import session_scope
from app.domain.enums import AgentStatus, MissionStatus
from app.domain.errors import InvalidTransitionError
from app.orchestration.state_machine import assert_transition, can_transition
from app.repositories import (
    AgentRepository,
    EventRepository,
    MissionRepository,
    OrganizationRepository,
)
from app.services.mission_service import mission_service


# --- state machine ------------------------------------------------------------
def test_valid_transitions_allowed() -> None:
    assert can_transition(MissionStatus.CREATED, MissionStatus.PLANNING)
    assert can_transition(MissionStatus.PLANNING, MissionStatus.ASSIGNED)
    assert can_transition(MissionStatus.ASSIGNED, MissionStatus.RUNNING)
    assert can_transition(MissionStatus.RUNNING, MissionStatus.WAITING_APPROVAL)
    assert can_transition(MissionStatus.WAITING_APPROVAL, MissionStatus.RUNNING)
    assert can_transition(MissionStatus.VALIDATING, MissionStatus.COMPLETED)


@pytest.mark.parametrize("bad", [
    (MissionStatus.CREATED, MissionStatus.COMPLETED),
    (MissionStatus.CREATED, MissionStatus.RUNNING),
    (MissionStatus.COMPLETED, MissionStatus.RUNNING),
    (MissionStatus.WAITING_APPROVAL, MissionStatus.COMPLETED),
])
def test_invalid_transitions_rejected(bad) -> None:
    current, target = bad
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransitionError):
        assert_transition(current, target)


# --- Scenario E — quarantine after three failures ----------------------------
def _new_mission() -> uuid.UUID:
    with session_scope() as session:
        org = OrganizationRepository(session).get_default()
        mission = MissionRepository(session).create(org.id, "Failure scenario mission", Decimal("5.00"))
        return mission.id


def test_repeated_failure_quarantines_agent_and_audits() -> None:
    mission_id = _new_mission()

    first = mission_service.record_task_failure(mission_id, "developer")
    second = mission_service.record_task_failure(mission_id, "developer")
    assert first == {"failure_count": 1, "quarantined": False}
    assert second == {"failure_count": 2, "quarantined": False}

    third = mission_service.record_task_failure(mission_id, "developer")
    assert third == {"failure_count": 3, "quarantined": True}

    with session_scope() as session:
        org = OrganizationRepository(session).get_default()
        agent = AgentRepository(session).get_by_key(org.id, "developer")
        assert agent.status is AgentStatus.QUARANTINED
        assert agent.failure_count == 3
        types = [e.type for e in EventRepository(session).list_for_mission(mission_id)]
    assert "agent.quarantined" in types
