"""Typed, versioned policy configuration — the ONLY source of the numbers.

Exact risk weights, level bands, and per-action decisions live here (backend
configuration), never in UI code. The config is hashed so any change to the
numbers changes the ``policy_hash`` recorded on every decision.

No dynamic evaluation: this is plain typed data, not code or expressions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from app.sentinel.enums import PolicyDecisionType, RiskLevel, SecurityActionType

POLICY_ID = "sentinel.entrance.default"
POLICY_VERSION = "1"

# Signed risk weights (points). Applied when the named factor is present.
DEFAULT_RISK_FACTORS: dict[str, int] = {
    "BUILDING_CLOSED": 25,
    "NO_EXPECTED_VISITOR": 20,
    "REPEATED_HUMAN_ACTIVITY": 15,
    "PROLONGED_ENTRANCE_ACTIVITY": 15,
    "NO_APPROVED_ACCESS_REQUEST": 15,
    "NO_VALID_CREDENTIAL": 10,
    "DELIVERY_EXPECTED": -15,
    "VERIFIED_VISITOR": -25,
}

# Inclusive upper bounds per level (score is clamped to 0..100).
DEFAULT_LEVEL_BOUNDS: dict[RiskLevel, int] = {
    RiskLevel.LOW: 24,
    RiskLevel.MEDIUM: 49,
    RiskLevel.HIGH: 74,
    RiskLevel.CRITICAL: 100,
}

# Default per-action decision. GRANT_TEMPORARY_ACCESS is conditional (see policy).
DEFAULT_ACTION_POLICY: dict[SecurityActionType, PolicyDecisionType] = {
    SecurityActionType.NOTIFY_OWNER: PolicyDecisionType.ALLOW,
    SecurityActionType.REQUEST_LIVE_REVIEW: PolicyDecisionType.ALLOW,
    SecurityActionType.CREATE_INCIDENT_NOTE: PolicyDecisionType.ALLOW,
    SecurityActionType.SEND_WARNING: PolicyDecisionType.REQUIRE_APPROVAL,
    SecurityActionType.NOTIFY_SECURITY: PolicyDecisionType.REQUIRE_APPROVAL,
    SecurityActionType.GRANT_TEMPORARY_ACCESS: PolicyDecisionType.DENY,
}

# Role required to approve a REQUIRE_APPROVAL action.
DEFAULT_APPROVAL_ROLES: dict[SecurityActionType, str] = {
    SecurityActionType.SEND_WARNING: "security",
    SecurityActionType.NOTIFY_SECURITY: "security",
}

# All four must hold for GRANT_TEMPORARY_ACCESS to be allowed.
GRANT_REQUIRED_CONDITIONS: tuple[str, ...] = (
    "time_policy_permits",
    "visitor_verified",
    "access_request_approved",
    "credential_valid",
)

# Risk at/above this band contributes RISK_TOO_HIGH to a grant denial.
RISK_TOO_HIGH_FROM: RiskLevel = RiskLevel.HIGH


@dataclass(frozen=True)
class PolicyConfig:
    policy_id: str = POLICY_ID
    version: str = POLICY_VERSION
    risk_factors: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_RISK_FACTORS))
    level_bounds: dict[RiskLevel, int] = field(default_factory=lambda: dict(DEFAULT_LEVEL_BOUNDS))
    action_policy: dict[SecurityActionType, PolicyDecisionType] = field(
        default_factory=lambda: dict(DEFAULT_ACTION_POLICY)
    )
    approval_roles: dict[SecurityActionType, str] = field(
        default_factory=lambda: dict(DEFAULT_APPROVAL_ROLES)
    )
    grant_conditions: tuple[str, ...] = GRANT_REQUIRED_CONDITIONS
    risk_too_high_from: RiskLevel = RISK_TOO_HIGH_FROM

    def level_for(self, score: int) -> RiskLevel:
        score = max(0, min(100, score))
        for level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
            if score <= self.level_bounds[level]:
                return level
        return RiskLevel.CRITICAL

    def canonical(self) -> str:
        payload = {
            "policy_id": self.policy_id,
            "version": self.version,
            "risk_factors": self.risk_factors,
            "level_bounds": {k.value: v for k, v in self.level_bounds.items()},
            "action_policy": {k.value: v.value for k, v in self.action_policy.items()},
            "approval_roles": {k.value: v for k, v in self.approval_roles.items()},
            "grant_conditions": list(self.grant_conditions),
            "risk_too_high_from": self.risk_too_high_from.value,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def hash(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()[:16]


# Process default. Swap for a different PolicyConfig to change the numbers.
DEFAULT_POLICY_CONFIG = PolicyConfig()
