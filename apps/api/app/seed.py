"""Idempotent seed data: one organization, the six-agent workforce, and policies.

Run via ``python -m app.seed`` (or ``make seed``). Safe to run repeatedly.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.session import session_scope
from app.domain.enums import DecisionResult
from app.repositories import AgentRepository, OrganizationRepository, PolicyRepository

ORG_NAME = "SwarmOps Demo Org"

AGENTS = [
    # key, name, role, team, allowed_tools, budget
    ("ceo", "CEO", "ceo", "Executive", ["plan.create"], Decimal("0.00")),
    ("pm", "Product Manager", "pm", "Product", ["tasks.decompose"], Decimal("0.00")),
    ("developer", "Developer", "developer", "Engineering", ["code.write", "production.deploy"], Decimal("1.00")),
    ("security", "Security", "security", "Governance", ["policy.enforce", "customer_database.export"], Decimal("1.00")),
    ("qa", "QA", "qa", "Quality", ["qa.run_tests"], Decimal("0.50")),
    ("finance", "Finance", "finance", "Cost Control", ["budget.review"], Decimal("0.00")),
]

POLICIES = [
    ("deployment.production.human_approval", "Production deployments require human approval.",
     DecisionResult.APPROVAL_REQUIRED, 70),
    ("data.production_export.restricted", "Unauthorized agents cannot export production customer data.",
     DecisionResult.BLOCK, 95),
    ("cost.budget.exceeded", "Projected cost exceeds the agent or mission budget.",
     DecisionResult.APPROVAL_REQUIRED, 55),
    ("agent.repeated_failure.quarantine", "Agents are quarantined after repeated task failures.",
     DecisionResult.BLOCK, 90),
    ("default.allow", "Action permitted by current policies.", DecisionResult.ALLOW, 10),
]


def seed(session: Session) -> dict[str, int]:
    orgs = OrganizationRepository(session)
    agents = AgentRepository(session)
    policies = PolicyRepository(session)

    org = orgs.get_default() or orgs.create(ORG_NAME)

    agent_count = 0
    for key, name, role, team, tools, budget in AGENTS:
        if agents.get_by_key(org.id, key) is None:
            agents.create(org.id, key, name, role, team, tools, budget)
            agent_count += 1

    for policy_id, desc, result, risk in POLICIES:
        policies.upsert(org.id, policy_id, desc, result, risk)

    return {"organization": 1, "agents_created": agent_count, "policies": len(POLICIES)}


def main() -> None:
    with session_scope() as session:
        summary = seed(session)
    print(f"Seed complete: {summary}")


if __name__ == "__main__":
    main()
