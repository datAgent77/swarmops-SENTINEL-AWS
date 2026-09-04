"""Deterministic entrance policy engine (authoritative; no LLM).

Maps an action + risk + context to ALLOW / REQUIRE_APPROVAL / DENY using only the
typed ``PolicyConfig``. GRANT_TEMPORARY_ACCESS is DENY unless every required
condition holds. Every decision records the policy id, version, and hash.

The AI's recommendation only selects WHICH action to evaluate; it never changes the
outcome — there is no code path by which a model can override this function.
"""

from __future__ import annotations

from datetime import datetime

from app.sentinel.enums import PolicyDecisionType, RiskLevel, SecurityActionType
from app.sentinel.governance.config import DEFAULT_POLICY_CONFIG, PolicyConfig
from app.sentinel.logic import access_preconditions
from app.sentinel.models import BuildingContext, PolicyDecision, RiskAssessment

_LEVEL_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


def _decision(
    action_type: SecurityActionType,
    decision: PolicyDecisionType,
    reason_codes: list[str],
    config: PolicyConfig,
) -> PolicyDecision:
    return PolicyDecision(
        decision=decision,
        reason_codes=reason_codes,
        policy_id=config.policy_id,
        policy_version=config.version,
        policy_hash=config.hash(),
        action_type=action_type,
    )


def evaluate_policy(
    action_type: SecurityActionType,
    risk: RiskAssessment,
    context: BuildingContext,
    now: datetime,
    config: PolicyConfig = DEFAULT_POLICY_CONFIG,
) -> PolicyDecision:
    if action_type is SecurityActionType.GRANT_TEMPORARY_ACCESS:
        return _evaluate_grant(action_type, risk, context, now, config)

    base = config.action_policy.get(action_type, PolicyDecisionType.DENY)
    if base is PolicyDecisionType.REQUIRE_APPROVAL:
        return _decision(action_type, base, ["HUMAN_APPROVAL_REQUIRED"], config)
    if base is PolicyDecisionType.ALLOW:
        return _decision(action_type, base, ["ALLOWED_BY_POLICY"], config)
    return _decision(action_type, PolicyDecisionType.DENY, ["DENIED_BY_POLICY"], config)


def _evaluate_grant(
    action_type: SecurityActionType,
    risk: RiskAssessment,
    context: BuildingContext,
    now: datetime,
    config: PolicyConfig,
) -> PolicyDecision:
    pre = access_preconditions(context, now)
    conditions = {
        "time_policy_permits": pre.within_business_hours,
        "visitor_verified": pre.verified_visitor,
        "access_request_approved": pre.approved_access_request,
        "credential_valid": pre.valid_credential,
    }
    missing = [name for name in config.grant_conditions if not conditions.get(name, False)]
    if not missing:
        return _decision(action_type, PolicyDecisionType.ALLOW, ["ALL_CONDITIONS_SATISFIED"], config)

    reason_codes = pre.failing_reason_codes()  # OUTSIDE_BUSINESS_HOURS, NO_VERIFIED_VISITOR, …
    if _LEVEL_ORDER[risk.risk_level] >= _LEVEL_ORDER[config.risk_too_high_from]:
        reason_codes.append("RISK_TOO_HIGH")
    return _decision(action_type, PolicyDecisionType.DENY, reason_codes, config)
