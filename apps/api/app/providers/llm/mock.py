"""Deterministic mock LLM provider.

Produces valid, persona-flavored structured JSON for each agent without any
network call. It is the default when no Gemini key is configured and the
automatic fallback when Gemini fails — so the demo always runs and always feels
like six collaborating AI employees, deterministically.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse, LLMUsage, estimate_tokens


def _objective(ctx: dict[str, Any]) -> str:
    return str(ctx.get("objective") or "the mission")


def _ceo(ctx: dict[str, Any]) -> dict:
    obj = _objective(ctx)
    return {
        "plan": f"Deliver '{obj}' in three phases: secure foundation, guarded implementation, "
                "and validated release. Ship behind human approval for anything touching production.",
        "reasoning": "Plan B keeps implementation risk low by gating the production deploy behind "
                     "human approval and enforcing data-governance policy before any customer data is touched.",
        "risks": ["Production exposure without review", "Unauthorized data access", "Scope creep"],
        "confidence": 0.86,
        "nextAgent": "pm",
    }


def _pm(ctx: dict[str, Any]) -> dict:
    return {
        "tasks": [
            "Implement authentication and portal shell",
            "Enforce production data governance policies",
            "Validate build and run QA tests",
            "Track budget and cost controls",
        ],
        "dependencies": ["auth precedes deploy", "QA precedes release"],
        "estimatedDuration": "2 sprints",
        "confidence": 0.82,
        "nextAgent": "developer",
    }


def _developer(ctx: dict[str, Any]) -> dict:
    if ctx.get("mode") == "fix":
        return {
            "implementation": "Patched the authentication edge case: tightened session validation and "
                              "added a regression test.",
            "risks": [],
            "toolRequests": [],
            "nextAgent": "qa",
        }
    return {
        "implementation": "Built the support-portal shell with authentication and a hardened API layer. "
                          "Ready to deploy to production.",
        "risks": ["Auth edge cases", "Deploy blast radius"],
        "toolRequests": ["production.deploy"],
        "nextAgent": "security",
    }


def _security(ctx: dict[str, Any]) -> dict:
    return {
        "securityReview": "Reviewed the deploy and data-access surface. Production customer export by a "
                          "non-privileged role must be denied by policy.",
        "violations": ["Attempted customer_database.export by an unauthorized role"],
        "recommendedActions": ["Rely on the deterministic governance engine to block the export", "Proceed to QA"],
    }


def _qa(ctx: dict[str, Any]) -> dict:
    if ctx.get("revalidate"):
        return {"issues": [], "severity": "none", "passed": True, "nextAgent": "finance"}
    return {
        "issues": ["Authentication edge case on concurrent sessions"],
        "severity": "medium",
        "passed": False,
        "nextAgent": "developer",
    }


def _finance(ctx: dict[str, Any]) -> dict:
    return {
        "estimatedCost": 0.82,
        "budgetStatus": "within_budget",
        "recommendation": "Approve. Projected spend is well under the mission budget with headroom for QA retries.",
    }


_BUILDERS = {
    "ceo": _ceo, "pm": _pm, "developer": _developer,
    "security": _security, "qa": _qa, "finance": _finance,
}


class MockProvider(LLMProvider):
    name = "mock"
    model = "mock-1"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        builder = _BUILDERS.get(request.schema_name or "")
        payload = builder(request.context) if builder else {"reasoning": "acknowledged", "nextAgent": None}
        text = json.dumps(payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = LLMUsage(
            input_tokens=estimate_tokens(request.system_prompt + request.user_prompt),
            output_tokens=estimate_tokens(text),
        )
        return LLMResponse(text=text, usage=usage, provider=self.name, model=self.model,
                           latency_ms=latency_ms, raw=payload)
