"""Deterministic entrance risk engine (authoritative; no LLM).

Scores a scene from the typed, configurable factors in ``config``. Pure function of
(observation, context, now, config): same inputs always yield the same score. The
factor set matches ``PolicyConfig.risk_factors``; only triggered factors contribute.
"""

from __future__ import annotations

from datetime import datetime

from app.sentinel.governance.config import DEFAULT_POLICY_CONFIG, PolicyConfig
from app.sentinel.logic import access_preconditions
from app.sentinel.models import BuildingContext, RiskAssessment, SecurityObservation


def _triggered(observation: SecurityObservation, context: BuildingContext, now: datetime) -> dict[str, bool]:
    pre = access_preconditions(context, now)
    return {
        "BUILDING_CLOSED": not context.building_open,
        "NO_EXPECTED_VISITOR": not pre.verified_visitor,
        "REPEATED_HUMAN_ACTIVITY": observation.repeated_activity and observation.person_present,
        "PROLONGED_ENTRANCE_ACTIVITY": observation.prolonged_presence,
        "NO_APPROVED_ACCESS_REQUEST": not pre.approved_access_request,
        "NO_VALID_CREDENTIAL": not pre.valid_credential,
        "DELIVERY_EXPECTED": context.delivery_expected,
        "VERIFIED_VISITOR": pre.verified_visitor,
    }


def assess_entrance_risk(
    observation: SecurityObservation,
    context: BuildingContext,
    now: datetime,
    config: PolicyConfig = DEFAULT_POLICY_CONFIG,
) -> RiskAssessment:
    triggered = _triggered(observation, context, now)
    factor_scores = {
        code: config.risk_factors[code]
        for code, is_on in triggered.items()
        if is_on and code in config.risk_factors
    }
    raw = sum(factor_scores.values())
    score = max(0, min(100, raw))
    pre = access_preconditions(context, now)
    return RiskAssessment(
        risk_score=score,
        risk_level=config.level_for(score),
        risk_factors=sorted(factor_scores),
        factor_scores=factor_scores,
        policy_context={
            **pre.model_dump(),
            "raw_score": raw,
            "policy_id": config.policy_id,
            "policy_version": config.version,
        },
    )
