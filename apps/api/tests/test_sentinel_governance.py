"""P04 tests: deterministic risk + policy engines (authoritative, no LLM)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.sentinel.enums import PolicyDecisionType, RiskLevel, SecurityActionType
from app.sentinel.governance.config import DEFAULT_POLICY_CONFIG, PolicyConfig
from app.sentinel.governance.risk import assess_entrance_risk
from app.sentinel.governance.service import evaluate_action, winner_scenario
from app.sentinel.models import (
    AccessRequest,
    BuildingContext,
    CredentialContext,
    SecurityObservation,
    VisitorContext,
)

NOW = datetime(2026, 1, 6, 23, 42, tzinfo=UTC)
A = SecurityActionType


def _obs(**over) -> SecurityObservation:
    base = dict(person_present=True, entrance_activity=True, confidence=0.9)
    base.update(over)
    return SecurityObservation(**base)


def _closed_scene_ctx() -> BuildingContext:
    return BuildingContext(
        building_open=False, expected_visitors=[], active_access_requests=[],
        credential_state=CredentialContext(presented=False, valid=False),
    )


def _fully_open_ctx() -> BuildingContext:
    return BuildingContext(
        building_open=True,
        expected_visitors=[VisitorContext(verified=True)],
        active_access_requests=[AccessRequest(approved=True, approved_by="security")],
        credential_state=CredentialContext(presented=True, valid=True),
    )


# --- risk factors + bounds ----------------------------------------------------

def test_all_positive_factors_max_out_at_critical():
    obs = _obs(prolonged_presence=True, repeated_activity=True)
    risk = assess_entrance_risk(obs, _closed_scene_ctx(), NOW)
    # 25+20+15+15+15+10 = 100
    assert risk.risk_score == 100
    assert risk.risk_level is RiskLevel.CRITICAL
    for code in ("BUILDING_CLOSED", "NO_EXPECTED_VISITOR", "REPEATED_HUMAN_ACTIVITY",
                 "PROLONGED_ENTRANCE_ACTIVITY", "NO_APPROVED_ACCESS_REQUEST", "NO_VALID_CREDENTIAL"):
        assert code in risk.factor_scores


def test_negative_factors_reduce_and_bounds_clamp():
    ctx = _fully_open_ctx().model_copy(update={"delivery_expected": True})
    risk = assess_entrance_risk(_obs(), ctx, NOW)
    assert risk.factor_scores.get("VERIFIED_VISITOR") == -25
    assert risk.factor_scores.get("DELIVERY_EXPECTED") == -15
    assert 0 <= risk.risk_score <= 100
    assert risk.risk_score == 0  # negatives clamp at 0
    assert risk.risk_level is RiskLevel.LOW


def test_level_bands_are_configurable_boundaries():
    cfg = DEFAULT_POLICY_CONFIG
    assert cfg.level_for(0) is RiskLevel.LOW
    assert cfg.level_for(24) is RiskLevel.LOW
    assert cfg.level_for(25) is RiskLevel.MEDIUM
    assert cfg.level_for(49) is RiskLevel.MEDIUM
    assert cfg.level_for(50) is RiskLevel.HIGH
    assert cfg.level_for(74) is RiskLevel.HIGH
    assert cfg.level_for(75) is RiskLevel.CRITICAL
    assert cfg.level_for(100) is RiskLevel.CRITICAL


# --- policy: ALLOW / REQUIRE_APPROVAL / DENY ----------------------------------

def test_allow_actions():
    ctx, obs = _closed_scene_ctx(), _obs()
    for action in (A.NOTIFY_OWNER, A.REQUEST_LIVE_REVIEW, A.CREATE_INCIDENT_NOTE):
        _, decision = evaluate_action(action, obs, ctx, NOW)
        assert decision.decision is PolicyDecisionType.ALLOW


def test_require_approval_actions():
    ctx, obs = _closed_scene_ctx(), _obs()
    for action in (A.SEND_WARNING, A.NOTIFY_SECURITY):
        _, decision = evaluate_action(action, obs, ctx, NOW)
        assert decision.decision is PolicyDecisionType.REQUIRE_APPROVAL
        assert "HUMAN_APPROVAL_REQUIRED" in decision.reason_codes


def test_grant_denied_when_conditions_missing():
    _, decision = evaluate_action(A.GRANT_TEMPORARY_ACCESS, _obs(prolonged_presence=True,
                                  repeated_activity=True), _closed_scene_ctx(), NOW)
    assert decision.decision is PolicyDecisionType.DENY
    for code in ("OUTSIDE_BUSINESS_HOURS", "NO_VERIFIED_VISITOR",
                 "NO_APPROVED_ACCESS_REQUEST", "NO_VALID_CREDENTIAL", "RISK_TOO_HIGH"):
        assert code in decision.reason_codes


def test_grant_allowed_only_when_all_conditions_hold():
    _, decision = evaluate_action(A.GRANT_TEMPORARY_ACCESS, _obs(), _fully_open_ctx(), NOW)
    assert decision.decision is PolicyDecisionType.ALLOW
    assert decision.reason_codes == ["ALL_CONDITIONS_SATISFIED"]


def test_each_missing_prerequisite_denies_with_its_reason():
    cases = {
        "OUTSIDE_BUSINESS_HOURS": {"building_open": False},
        "NO_VERIFIED_VISITOR": {"expected_visitors": []},
        "NO_APPROVED_ACCESS_REQUEST": {"active_access_requests": []},
        "NO_VALID_CREDENTIAL": {"credential_state": CredentialContext(presented=False, valid=False)},
    }
    for expected_code, override in cases.items():
        ctx = _fully_open_ctx().model_copy(update=override)
        _, decision = evaluate_action(A.GRANT_TEMPORARY_ACCESS, _obs(), ctx, NOW)
        assert decision.decision is PolicyDecisionType.DENY
        assert expected_code in decision.reason_codes


# --- versioning + hash --------------------------------------------------------

def test_decision_carries_policy_version_and_hash():
    _, decision = evaluate_action(A.GRANT_TEMPORARY_ACCESS, _obs(), _closed_scene_ctx(), NOW)
    assert decision.policy_id == "sentinel.entrance.default"
    assert decision.policy_version == "1"
    assert decision.policy_hash and len(decision.policy_hash) == 16


def test_policy_hash_changes_with_the_numbers():
    base = DEFAULT_POLICY_CONFIG.hash()
    tweaked = PolicyConfig(risk_factors={**DEFAULT_POLICY_CONFIG.risk_factors, "BUILDING_CLOSED": 30})
    assert tweaked.hash() != base


# --- AI recommendation cannot override policy ---------------------------------

def test_ai_recommendation_conflict_is_ignored():
    # The AI recommends GRANT; policy denies regardless of the recommendation.
    _, decision = evaluate_action(A.GRANT_TEMPORARY_ACCESS, _obs(confidence=0.99), _closed_scene_ctx(), NOW)
    assert decision.decision is PolicyDecisionType.DENY


# --- GOLDEN: same inputs → same DENY, repeated --------------------------------

def test_golden_winner_scenario_is_repeatably_deny():
    first = winner_scenario()
    assert first["grant_denied"] is True
    grant = first["decisions"]["grant_temporary_access"]
    assert grant["decision"] == "DENY"

    for _ in range(25):
        again = winner_scenario()["decisions"]["grant_temporary_access"]
        assert again["decision"] == "DENY"
        assert again["reason_codes"] == grant["reason_codes"]
        assert again["policy_hash"] == grant["policy_hash"]


# --- API ----------------------------------------------------------------------

def test_api_winner_scenario_real_backend_deny():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = client.get("/api/governance/winner-scenario").json()
    assert body["ai_recommendation"] == "GRANT_TEMPORARY_ACCESS"
    assert body["grant_denied"] is True
    assert body["decisions"]["grant_temporary_access"]["decision"] == "DENY"
    assert "NO_VERIFIED_VISITOR" in body["decisions"]["grant_temporary_access"]["reason_codes"]


def test_api_policy_exposes_version_and_hash():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = client.get("/api/governance/policy").json()
    assert body["policy_id"] == "sentinel.entrance.default"
    assert body["version"] == "1"
    assert len(body["hash"]) == 16
