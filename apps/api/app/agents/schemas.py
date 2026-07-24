"""Structured agent outputs. Agents must return JSON matching these models;
invalid output is rejected and retried by the agent runner.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError


class CEOOutput(BaseModel):
    plan: str
    reasoning: str
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    nextAgent: str | None = None


class PMOutput(BaseModel):
    tasks: list[str]
    dependencies: list[str] = Field(default_factory=list)
    estimatedDuration: str
    confidence: float = Field(ge=0.0, le=1.0)
    nextAgent: str | None = None


class DeveloperOutput(BaseModel):
    implementation: str
    risks: list[str] = Field(default_factory=list)
    toolRequests: list[str] = Field(default_factory=list)
    nextAgent: str | None = None


class QAOutput(BaseModel):
    issues: list[str] = Field(default_factory=list)
    severity: str
    passed: bool
    nextAgent: str | None = None


class SecurityOutput(BaseModel):
    securityReview: str
    violations: list[str] = Field(default_factory=list)
    recommendedActions: list[str] = Field(default_factory=list)


class FinanceOutput(BaseModel):
    estimatedCost: float
    budgetStatus: str
    recommendation: str


class StructuredOutputError(ValueError):
    """Raised when an LLM response is not valid JSON for the expected schema."""


def parse_structured(text: str, model: type[BaseModel]) -> BaseModel:
    """Parse and validate JSON text into a schema, raising StructuredOutputError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f"response was not valid JSON: {exc}") from exc
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(f"response did not match {model.__name__}: {exc}") from exc
