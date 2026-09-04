"""Sentinel governance routes — the authoritative decision surface.

Real, deterministic policy evaluation. No LLM participates; the AI recommendation
only names the action to evaluate. Every response carries policy id/version/hash.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.sentinel.enums import SecurityActionType
from app.sentinel.governance.config import DEFAULT_POLICY_CONFIG
from app.sentinel.governance.service import evaluate_action, winner_scenario
from app.sentinel.models import (
    AccessRequest,
    BuildingContext,
    CredentialContext,
    SecurityObservation,
    VisitorContext,
)

router = APIRouter(prefix="/api/governance", tags=["governance"])


class EvaluateRequest(BaseModel):
    action_type: str = "GRANT_TEMPORARY_ACCESS"
    # context (facts, never inferred from AI)
    building_open: bool = False
    delivery_expected: bool = False
    verified_visitor: bool = False
    approved_access_request: bool = False
    valid_credential: bool = False
    # observation (perception input to risk only)
    person_present: bool = True
    prolonged_presence: bool = False
    repeated_activity: bool = False
    package_present: bool = False
    vehicle_present: bool = False


def _context(body: EvaluateRequest) -> BuildingContext:
    return BuildingContext(
        building_open=body.building_open,
        delivery_expected=body.delivery_expected,
        expected_visitors=[VisitorContext(verified=True)] if body.verified_visitor else [],
        active_access_requests=[AccessRequest(approved=True, approved_by="security")]
        if body.approved_access_request else [],
        credential_state=CredentialContext(presented=body.valid_credential, valid=body.valid_credential),
    )


def _observation(body: EvaluateRequest) -> SecurityObservation:
    return SecurityObservation(
        person_present=body.person_present, prolonged_presence=body.prolonged_presence,
        repeated_activity=body.repeated_activity, package_present=body.package_present,
        vehicle_present=body.vehicle_present, entrance_activity=body.person_present,
        confidence=0.9,
    )


@router.get("/policy")
async def policy() -> dict:
    cfg = DEFAULT_POLICY_CONFIG
    return {
        "policy_id": cfg.policy_id,
        "version": cfg.version,
        "hash": cfg.hash(),
        "risk_factors": cfg.risk_factors,
        "level_bounds": {k.value: v for k, v in cfg.level_bounds.items()},
        "action_policy": {k.value: v.value for k, v in cfg.action_policy.items()},
        "grant_conditions": list(cfg.grant_conditions),
    }


@router.post("/evaluate")
async def evaluate(body: EvaluateRequest) -> dict:
    try:
        action = SecurityActionType(body.action_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"unknown action_type '{body.action_type}'") from exc
    risk, decision = evaluate_action(action, _observation(body), _context(body))
    return {"risk": risk.model_dump(), "decision": decision.model_dump()}


@router.get("/winner-scenario")
async def winner() -> dict:
    return winner_scenario()
