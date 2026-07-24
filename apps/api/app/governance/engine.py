"""Deterministic governance engine — the single, centralized policy authority.

Policies are enforced here and only here. The engine is a pure function of its
input: no I/O, no randomness, no time dependence. LLMs may later *explain* a
decision, but they never change the outcome. Every branch maps to a stable
policy_id and risk score so decisions are auditable and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import DecisionResult, Environment

# Roles explicitly permitted to export production customer data.
AUTHORIZED_EXPORT_ROLES: frozenset[str] = frozenset({"security", "data_admin"})

# An agent that fails the same task this many times is quarantined.
QUARANTINE_THRESHOLD: int = 3


@dataclass(frozen=True)
class ActionRequest:
    tool: str
    agent_role: str
    environment: str = Environment.PRODUCTION.value
    resource: str | None = None
    estimated_cost_usd: float = 0.0
    agent_budget_usd: float | None = None
    agent_spent_usd: float = 0.0
    mission_budget_usd: float | None = None
    mission_spent_usd: float = 0.0
    agent_id: str | None = None


@dataclass(frozen=True)
class Decision:
    result: DecisionResult
    risk_score: int
    reason: str
    policy_id: str
    details: dict = field(default_factory=dict)


class GovernanceEngine:
    """Evaluates a single agent action against deterministic policy."""

    quarantine_threshold: int = QUARANTINE_THRESHOLD

    def evaluate(self, request: ActionRequest) -> Decision:
        # Scenario A — Production deployment requires human approval.
        if request.tool == "production.deploy" and request.environment == Environment.PRODUCTION.value:
            return Decision(
                result=DecisionResult.APPROVAL_REQUIRED,
                risk_score=70,
                reason="Production deployments require human approval.",
                policy_id="deployment.production.human_approval",
            )

        # Scenario B — Unauthorized production customer export is blocked.
        if request.tool == "customer_database.export" and request.agent_role not in AUTHORIZED_EXPORT_ROLES:
            return Decision(
                result=DecisionResult.BLOCK,
                risk_score=95,
                reason="Unauthorized agents cannot export production customer data.",
                policy_id="data.production_export.restricted",
            )

        # Scenario D — Projected cost exceeds the agent or mission budget.
        if self._exceeds_budget(request):
            return Decision(
                result=DecisionResult.APPROVAL_REQUIRED,
                risk_score=55,
                reason="Projected cost exceeds the agent or mission budget.",
                policy_id="cost.budget.exceeded",
            )

        # Scenario C (and default) — Allow with low risk.
        return Decision(
            result=DecisionResult.ALLOW,
            risk_score=10,
            reason="Action permitted by current policies.",
            policy_id="default.allow",
        )

    def _exceeds_budget(self, request: ActionRequest) -> bool:
        cost = request.estimated_cost_usd
        if cost <= 0:
            return False
        if request.agent_budget_usd is not None and cost > request.agent_budget_usd:
            return True
        if (
            request.mission_budget_usd is not None
            and request.mission_spent_usd + cost > request.mission_budget_usd
        ):
            return True
        return False

    # Scenario E — Repeated failure quarantine (deterministic threshold).
    def is_quarantined(self, failure_count: int) -> bool:
        return failure_count >= self.quarantine_threshold
