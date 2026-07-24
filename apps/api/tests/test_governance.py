"""Deterministic governance engine — Scenarios A through E.

The engine is the enforcement core of the demo. These tests pin the exact
result, risk score, and reason for each governed scenario.
"""

import pytest

from app.domain.enums import DecisionResult
from app.governance.engine import ActionRequest, GovernanceEngine


@pytest.fixture
def engine() -> GovernanceEngine:
    return GovernanceEngine()


# --- Scenario A — Production deployment ---------------------------------------
def test_scenario_a_production_deploy_requires_approval(engine: GovernanceEngine) -> None:
    decision = engine.evaluate(
        ActionRequest(tool="production.deploy", agent_role="developer", environment="production")
    )
    assert decision.result is DecisionResult.APPROVAL_REQUIRED
    assert decision.risk_score == 70
    assert decision.reason == "Production deployments require human approval."
    assert decision.policy_id == "deployment.production.human_approval"


# --- Scenario B — Unauthorized customer export --------------------------------
@pytest.mark.parametrize("role", ["developer", "marketing", "pm", "qa", "ceo", "finance"])
def test_scenario_b_unauthorized_export_blocked(engine: GovernanceEngine, role: str) -> None:
    decision = engine.evaluate(
        ActionRequest(tool="customer_database.export", agent_role=role, environment="production")
    )
    assert decision.result is DecisionResult.BLOCK
    assert decision.risk_score == 95
    assert decision.reason == "Unauthorized agents cannot export production customer data."
    assert decision.policy_id == "data.production_export.restricted"


@pytest.mark.parametrize("role", ["security", "data_admin"])
def test_authorized_roles_may_export(engine: GovernanceEngine, role: str) -> None:
    decision = engine.evaluate(ActionRequest(tool="customer_database.export", agent_role=role))
    assert decision.result is DecisionResult.ALLOW


# --- Scenario C — QA tests ----------------------------------------------------
def test_scenario_c_qa_run_tests_allowed(engine: GovernanceEngine) -> None:
    decision = engine.evaluate(ActionRequest(tool="qa.run_tests", agent_role="qa"))
    assert decision.result is DecisionResult.ALLOW
    assert decision.risk_score == 10


# --- Scenario D — Budget overflow ---------------------------------------------
def test_scenario_d_cost_exceeds_agent_budget(engine: GovernanceEngine) -> None:
    decision = engine.evaluate(
        ActionRequest(tool="model.invoke", agent_role="developer",
                      estimated_cost_usd=2.0, agent_budget_usd=1.0)
    )
    assert decision.result is DecisionResult.APPROVAL_REQUIRED
    assert decision.policy_id == "cost.budget.exceeded"


def test_scenario_d_cost_exceeds_mission_budget(engine: GovernanceEngine) -> None:
    decision = engine.evaluate(
        ActionRequest(tool="model.invoke", agent_role="developer",
                      estimated_cost_usd=1.0, agent_budget_usd=10.0,
                      mission_budget_usd=5.0, mission_spent_usd=4.5)
    )
    assert decision.result is DecisionResult.APPROVAL_REQUIRED
    assert decision.policy_id == "cost.budget.exceeded"


def test_cost_within_budget_is_allowed(engine: GovernanceEngine) -> None:
    decision = engine.evaluate(
        ActionRequest(tool="model.invoke", agent_role="developer",
                      estimated_cost_usd=0.5, agent_budget_usd=1.0,
                      mission_budget_usd=5.0, mission_spent_usd=1.0)
    )
    assert decision.result is DecisionResult.ALLOW


# --- Scenario E — Repeated failure quarantine ---------------------------------
def test_scenario_e_quarantine_threshold(engine: GovernanceEngine) -> None:
    assert engine.is_quarantined(0) is False
    assert engine.is_quarantined(2) is False
    assert engine.is_quarantined(3) is True
    assert engine.is_quarantined(4) is True


# --- Determinism guarantee ----------------------------------------------------
def test_engine_is_deterministic(engine: GovernanceEngine) -> None:
    req = ActionRequest(tool="production.deploy", agent_role="developer")
    first = engine.evaluate(req)
    for _ in range(5):
        assert engine.evaluate(req) == first
