"""P01 domain tests for Sentinel (pure domain; no Ring, Bedrock, or final policy)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.domain.errors import InvalidTransitionError
from app.sentinel.enums import (
    ActionProvider,
    ActionStatus,
    ApprovalStatus,
    AuditActorType,
    IncidentStatus,
    PolicyDecisionType,
    RiskLevel,
    SecurityActionType,
    SecurityEventType,
)
from app.sentinel.lifecycle import assert_transition, can_transition
from app.sentinel.logic import access_preconditions, compute_risk, correlate_events
from app.sentinel.models import (
    AccessRequest,
    ApprovalRequest,
    AuditEvent,
    BuildingContext,
    CredentialContext,
    PolicyDecision,
    RiskAssessment,
    SecurityAction,
    SecurityEvent,
    SecurityIncident,
    SecurityObservation,
    VisitorContext,
)

# 23:42 on a Tuesday (2026-01-06), building closed — the canonical scene.
SCENE_AT = datetime(2026, 1, 6, 23, 42, tzinfo=UTC)


def _event(mins: int, location: str = "loc-1", device: str = "dev-1") -> SecurityEvent:
    return SecurityEvent(
        location_id=location, device_id=device, type=SecurityEventType.MOTION,
        occurred_at=SCENE_AT + timedelta(minutes=mins),
    )


# --- incident lifecycle -------------------------------------------------------

def test_incident_valid_transitions():
    inc = SecurityIncident(location_id="loc-1")
    assert inc.status is IncidentStatus.DETECTED
    inc.transition(IncidentStatus.OBSERVING)
    inc.transition(IncidentStatus.ASSESSING)
    inc.transition(IncidentStatus.ESCALATED)
    inc.transition(IncidentStatus.AWAITING_APPROVAL)
    inc.transition(IncidentStatus.ACTIONED)
    inc.transition(IncidentStatus.RESOLVED)
    assert inc.status is IncidentStatus.RESOLVED


def test_incident_invalid_transition_raises():
    inc = SecurityIncident(location_id="loc-1")
    with pytest.raises(InvalidTransitionError):
        inc.transition(IncidentStatus.ACTIONED)  # cannot skip straight from DETECTED


def test_incident_terminal_has_no_exits():
    for terminal in (IncidentStatus.RESOLVED, IncidentStatus.DISMISSED):
        assert not any(can_transition(terminal, s) for s in IncidentStatus)
    with pytest.raises(InvalidTransitionError):
        assert_transition(IncidentStatus.RESOLVED, IncidentStatus.OBSERVING)


def test_dismiss_reachable_from_nonterminal():
    inc = SecurityIncident(location_id="loc-1")
    inc.transition(IncidentStatus.OBSERVING)
    inc.transition(IncidentStatus.DISMISSED)
    assert inc.status is IncidentStatus.DISMISSED


# --- event grouping -----------------------------------------------------------

def test_events_within_window_group_into_one_incident():
    groups = correlate_events([_event(0), _event(2), _event(5)])  # 23:42, 23:44, 23:47
    assert len(groups) == 1
    assert len(groups[0]) == 3


def test_events_beyond_window_split():
    groups = correlate_events([_event(0), _event(2), _event(30)], window_seconds=300)
    assert len(groups) == 2
    assert [len(g) for g in sorted(groups, key=len, reverse=True)] == [2, 1]


def test_events_at_different_locations_never_merge():
    groups = correlate_events([_event(0, "loc-1"), _event(1, "loc-2")])
    assert len(groups) == 2


def test_correlation_is_order_independent():
    a = correlate_events([_event(0), _event(2), _event(5)])
    b = correlate_events([_event(5), _event(0), _event(2)])
    assert len(a) == len(b) == 1 and len(a[0]) == len(b[0]) == 3


def test_incident_add_event_dedupes_and_tracks_devices():
    inc = SecurityIncident(location_id="loc-1")
    ev = _event(0)
    inc.add_event(ev)
    inc.add_event(ev)  # idempotent
    assert inc.event_ids == [ev.event_id]
    assert inc.device_ids == [ev.device_id]


# --- risk model ---------------------------------------------------------------

def _closed_high_risk_observation() -> SecurityObservation:
    return SecurityObservation(
        person_present=True, entrance_activity=True, prolonged_presence=True,
        repeated_activity=True, confidence=0.91, summary="Person lingering at a closed entrance.",
    )


def test_risk_is_deterministic_and_recomputable():
    obs, ctx = _closed_high_risk_observation(), BuildingContext(building_open=False)
    r1 = compute_risk(obs, ctx, SCENE_AT)
    r2 = compute_risk(obs, ctx, SCENE_AT)
    assert r1.risk_score == r2.risk_score
    assert r1.factor_scores == r2.factor_scores
    assert r1.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert r1.risk_score == min(100, sum(r1.factor_scores.values()))


def test_risk_serialization_round_trip():
    r = compute_risk(_closed_high_risk_observation(), BuildingContext(building_open=False), SCENE_AT)
    restored = RiskAssessment.model_validate(r.model_dump())
    assert restored == r


def test_low_risk_when_open_and_quiet():
    obs = SecurityObservation(person_present=True, confidence=0.9)
    r = compute_risk(obs, BuildingContext(building_open=True), SCENE_AT)
    assert r.risk_level is RiskLevel.LOW


# --- observation must never carry authorization -------------------------------

@pytest.mark.parametrize("bad", ["allow_access", "deny_access", "approved", "authorized", "unlock"])
def test_observation_rejects_authorization_fields(bad):
    with pytest.raises(ValidationError):
        SecurityObservation(person_present=True, **{bad: True})


def test_observation_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        SecurityObservation(person_present=True, made_up_field=1)


# --- policy decision serialization --------------------------------------------

def test_policy_decision_serialization():
    d = PolicyDecision(
        decision=PolicyDecisionType.DENY,
        reason_codes=["OUTSIDE_BUSINESS_HOURS", "NO_VERIFIED_VISITOR"],
        policy_id="access.entrance.default", policy_version="1", policy_hash="abc123",
        action_type=SecurityActionType.GRANT_TEMPORARY_ACCESS,
    )
    restored = PolicyDecision.model_validate(d.model_dump())
    assert restored == d
    assert restored.decision is PolicyDecisionType.DENY


# --- approval expiry ----------------------------------------------------------

def test_approval_expiry():
    past = SCENE_AT - timedelta(minutes=1)
    appr = ApprovalRequest(
        incident_id="inc-1", action_id="act-1", required_role="security", expires_at=past
    )
    assert appr.is_expired(SCENE_AT) is True


def test_approval_not_expired_when_resolved_or_future():
    future = ApprovalRequest(
        incident_id="inc-1", action_id="act-1", required_role="security",
        expires_at=SCENE_AT + timedelta(minutes=5),
    )
    assert future.is_expired(SCENE_AT) is False
    approved = ApprovalRequest(
        incident_id="inc-1", action_id="act-1", required_role="security",
        status=ApprovalStatus.APPROVED, expires_at=SCENE_AT - timedelta(minutes=1),
    )
    assert approved.is_expired(SCENE_AT) is False  # only PENDING can expire


# --- action lifecycle: intent vs provider -------------------------------------

def test_action_default_provider_separates_intent_from_provider():
    warn = SecurityAction(incident_id="inc-1", type=SecurityActionType.SEND_WARNING)
    assert warn.provider is ActionProvider.SECURITY_TEAM
    assert warn.status is ActionStatus.RECOMMENDED

    grant = SecurityAction(incident_id="inc-1", type=SecurityActionType.GRANT_TEMPORARY_ACCESS)
    # A physical action a smart lock performs — never Ring, never the AI itself.
    assert grant.provider is ActionProvider.SMART_LOCK
    assert grant.provider is not ActionProvider.RING


def test_action_explicit_provider_is_respected():
    a = SecurityAction(
        incident_id="inc-1", type=SecurityActionType.NOTIFY_OWNER, provider=ActionProvider.OWNER_APP
    )
    assert a.provider is ActionProvider.OWNER_APP


# --- audit schema -------------------------------------------------------------

def test_audit_event_schema():
    e = AuditEvent(
        incident_id="inc-1", actor_type=AuditActorType.OFFICER, actor_id="sentinel",
        action="incident.assessed", decision="REQUIRE_APPROVAL", reason="risk high",
        metadata={"risk_score": 85},
    )
    restored = AuditEvent.model_validate(e.model_dump())
    assert restored == e
    assert restored.actor_type is AuditActorType.OFFICER


# --- GOLDEN: the 23:42 scene must be capable of a deterministic DENY ----------

def test_golden_2342_closed_building_supports_deterministic_deny():
    # Building closed, no expected visitor, no active access request, no valid credential.
    context = BuildingContext(
        building_open=False,
        expected_visitors=[],
        active_access_requests=[],
        credential_state=CredentialContext(presented=False, valid=False),
    )
    pre = access_preconditions(context, SCENE_AT)

    assert pre.all_satisfied is False
    assert pre.failing_reason_codes() == [
        "OUTSIDE_BUSINESS_HOURS",
        "NO_VERIFIED_VISITOR",
        "NO_APPROVED_ACCESS_REQUEST",
        "NO_VALID_CREDENTIAL",
    ]

    # And the incident can be assembled and driven to an assessed state.
    incident = SecurityIncident(location_id="loc-1")
    for mins in (0, 2, 5):
        incident.add_event(_event(mins))
    incident.observation = _closed_high_risk_observation()
    incident.context = context
    incident.risk = compute_risk(incident.observation, context, SCENE_AT)
    incident.transition(IncidentStatus.OBSERVING)
    incident.transition(IncidentStatus.ASSESSING)

    assert len(incident.event_ids) == 3
    assert incident.risk.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    # Perception carries no authority; the deterministic preconditions do.
    assert incident.risk.policy_context["all_satisfied"] is False


def test_golden_daytime_with_credential_can_satisfy_preconditions():
    """Sanity counterpart: when every fact holds, preconditions pass (no DENY basis)."""
    now = datetime(2026, 1, 6, 10, 0, tzinfo=UTC)
    context = BuildingContext(
        building_open=True,
        expected_visitors=[VisitorContext(name="Courier", verified=True)],
        active_access_requests=[AccessRequest(approved=True, approved_by="security")],
        credential_state=CredentialContext(presented=True, valid=True),
    )
    pre = access_preconditions(context, now)
    assert pre.all_satisfied is True
    assert pre.failing_reason_codes() == []
