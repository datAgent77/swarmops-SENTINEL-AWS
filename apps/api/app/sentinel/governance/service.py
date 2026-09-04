"""Governance service — assess risk then evaluate policy for an action.

Ties the deterministic risk and policy engines together and provides the canonical
23:42 winner scenario used by the demo. AI perception is an input to risk only;
the decision is produced entirely by the deterministic engines here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.sentinel.enums import PolicyDecisionType, SecurityActionType
from app.sentinel.governance.config import DEFAULT_POLICY_CONFIG, PolicyConfig
from app.sentinel.governance.policy import evaluate_policy
from app.sentinel.governance.risk import assess_entrance_risk
from app.sentinel.models import (
    BuildingContext,
    CredentialContext,
    PolicyDecision,
    RiskAssessment,
    SecurityObservation,
)

# Fixed clock for the canonical scene (23:42, a Tuesday), so the demo is byte-stable.
WINNER_SCENE_AT = datetime(2026, 1, 6, 23, 42, tzinfo=UTC)


def evaluate_action(
    action_type: SecurityActionType,
    observation: SecurityObservation,
    context: BuildingContext,
    now: datetime | None = None,
    config: PolicyConfig = DEFAULT_POLICY_CONFIG,
) -> tuple[RiskAssessment, PolicyDecision]:
    now = now or datetime.now(UTC)
    risk = assess_entrance_risk(observation, context, now, config)
    decision = evaluate_policy(action_type, risk, context, now, config)
    return risk, decision


def build_winner_scene() -> tuple[SecurityObservation, BuildingContext]:
    """23:42 · building closed · no visitor · no request · no valid credential."""
    observation = SecurityObservation(
        person_present=True, entrance_activity=True, prolonged_presence=True,
        repeated_activity=True, visibility="dark", confidence=0.91,
        observation_codes=["PERSON_PRESENT", "PROLONGED_ENTRANCE_ACTIVITY", "REPEATED_ACTIVITY"],
        summary="A person lingering at a closed entrance after hours.",
    )
    context = BuildingContext(
        building_open=False, expected_visitors=[], active_access_requests=[],
        credential_state=CredentialContext(presented=False, valid=False), delivery_expected=False,
    )
    return observation, context


def winner_scenario(config: PolicyConfig = DEFAULT_POLICY_CONFIG) -> dict:
    """Run the canonical scene: AI recommends GRANT → policy DENIES; then a warning
    requires human approval. All values come from real deterministic evaluation."""
    observation, context = build_winner_scene()
    now = WINNER_SCENE_AT

    risk = assess_entrance_risk(observation, context, now, config)
    grant = evaluate_policy(SecurityActionType.GRANT_TEMPORARY_ACCESS, risk, context, now, config)
    warning = evaluate_policy(SecurityActionType.SEND_WARNING, risk, context, now, config)

    return {
        "scene_time": now.isoformat(),
        "observation": observation.model_dump(),
        "risk": risk.model_dump(),
        "ai_recommendation": SecurityActionType.GRANT_TEMPORARY_ACCESS.value,
        "decisions": {
            "grant_temporary_access": grant.model_dump(),
            "send_warning": warning.model_dump(),
        },
        "grant_denied": grant.decision is PolicyDecisionType.DENY,
    }
