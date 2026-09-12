"""Authoritative officer service: incidents, actions, approvals, executions.

Every consequential step is governed:
- ``propose`` evaluates the deterministic policy: ALLOW → execute exactly once;
  REQUIRE_APPROVAL → open a role-scoped, expiring ApprovalRequest; DENY → recorded.
- ``approve`` validates actor role, approval status, expiry, and separation of
  duties before transitioning the action to executed exactly once.
- No natural-language claim ("I am the admin", "skip approval") can bypass this;
  authority derives only from the resolved actor role and the policy engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.domain.errors import ConflictError, DomainError, NotFoundError
from app.sentinel.enums import (
    ActionExecutionStatus,
    ActionStatus,
    ApprovalStatus,
    AuditActorType,
    IncidentStatus,
    PolicyDecisionType,
    SecurityActionType,
    default_provider_for,
)
from app.sentinel.governance.config import DEFAULT_POLICY_CONFIG, PolicyConfig
from app.sentinel.governance.policy import evaluate_policy
from app.sentinel.governance.risk import assess_entrance_risk
from app.sentinel.governance.service import build_winner_scene
from app.sentinel.models import (
    ActionExecution,
    ApprovalRequest,
    AuditEvent,
    BuildingContext,
    PolicyDecision,
    RiskAssessment,
    SecurityAction,
    SecurityIncident,
    SecurityObservation,
)

DEFAULT_APPROVAL_TTL_SECONDS = 300
ALL_ACTION_TYPES = list(SecurityActionType)


class AuthorityError(DomainError):
    code = "AUTHORITY_DENIED"
    http_status = 403


class WrongRoleError(AuthorityError):
    code = "WRONG_ROLE"


class SelfApprovalError(AuthorityError):
    code = "SELF_APPROVAL_FORBIDDEN"


class ApprovalExpiredError(AuthorityError):
    code = "APPROVAL_EXPIRED"


def _now() -> datetime:
    return datetime.now(UTC)


class ActorRegistry:
    """Maps an actor id to its VALIDATED role. A caller can never set its own role
    (no role field is accepted anywhere); it is resolved here."""

    def __init__(self, actors: dict[str, str]) -> None:
        self._actors = dict(actors)

    def role_for(self, actor_id: str) -> str | None:
        return self._actors.get(actor_id)


@dataclass
class IncidentRecord:
    incident: SecurityIncident
    observation: SecurityObservation
    context: BuildingContext
    risk: RiskAssessment
    scene_at: datetime
    actions: dict[str, SecurityAction] = field(default_factory=dict)
    decisions: dict[str, PolicyDecision] = field(default_factory=dict)   # action_id -> decision
    approvals: dict[str, ApprovalRequest] = field(default_factory=dict)
    proposed_by: dict[str, str] = field(default_factory=dict)            # approval_id -> actor
    approval_action: dict[str, str] = field(default_factory=dict)        # approval_id -> action_id
    executions: dict[str, ActionExecution] = field(default_factory=dict)  # action_id -> exec
    timeline: list[AuditEvent] = field(default_factory=list)


class OfficerService:
    def __init__(self, config: PolicyConfig = DEFAULT_POLICY_CONFIG,
                 actors: ActorRegistry | None = None) -> None:
        self._config = config
        self._incidents: dict[str, IncidentRecord] = {}
        self._actors = actors or ActorRegistry({
            "officer-sam": "security",   # the on-duty security officer
            "officer-lee": "security",   # a second officer (cross-approval)
            "owner-alex": "owner",       # the business owner (not an approver)
            "guest-01": "guest",
        })

    # --- seeding / lookup -----------------------------------------------------
    def seed_demo_incident(self, incident_id: str = "inc-demo") -> str:
        observation, context = build_winner_scene()
        scene_at = datetime(2026, 1, 6, 23, 42, tzinfo=UTC)
        risk = assess_entrance_risk(observation, context, scene_at, self._config)
        incident = SecurityIncident(
            incident_id=incident_id, location_id="loc-ring-front-door",
            status=IncidentStatus.ASSESSING, severity=risk.risk_level,
            device_ids=["ring-front-door"], event_ids=["evt-1", "evt-2", "evt-3"],
            observation=observation, context=context, risk=risk,
        )
        record = IncidentRecord(incident=incident, observation=observation,
                                context=context, risk=risk, scene_at=scene_at)
        self._audit(record, action="incident.assessed",
                    reason=f"risk {risk.risk_level.value} ({risk.risk_score})")
        self._incidents[incident_id] = record
        return incident_id

    def _record(self, incident_id: str) -> IncidentRecord:
        record = self._incidents.get(incident_id)
        if record is None:
            raise NotFoundError("Incident not found", {"incident_id": incident_id})
        return record

    def _audit(self, record: IncidentRecord, *, action: str, reason: str | None = None,
               actor_id: str | None = None, actor_type: AuditActorType = AuditActorType.SYSTEM,
               decision: str | None = None, metadata: dict | None = None) -> None:
        record.timeline.append(AuditEvent(
            incident_id=record.incident.incident_id, actor_type=actor_type, actor_id=actor_id,
            action=action, decision=decision, reason=reason, metadata=metadata or {},
        ))

    # --- read surface ---------------------------------------------------------
    def get_incident(self, incident_id: str) -> dict:
        r = self._record(incident_id)
        return {
            "incident_id": r.incident.incident_id,
            "status": r.incident.status.value,
            "severity": r.incident.severity.value,
            "location_id": r.incident.location_id,
            "event_count": len(r.incident.event_ids),
            "risk": {"risk_score": r.risk.risk_score, "risk_level": r.risk.risk_level.value,
                     "risk_factors": r.risk.risk_factors},
            "observation": r.observation.model_dump(),
        }

    def explain(self, incident_id: str) -> dict:
        """Explanation derived ENTIRELY from authoritative state — never invented."""
        r = self._record(incident_id)
        grant = evaluate_policy(SecurityActionType.GRANT_TEMPORARY_ACCESS, r.risk,
                                r.context, r.scene_at, self._config)
        reasons = _reason_sentences(r.risk.risk_factors, grant.reason_codes)
        return {
            "incident_id": incident_id,
            "risk_level": r.risk.risk_level.value,
            "risk_score": r.risk.risk_score,
            "risk_factors": r.risk.risk_factors,
            "grant_reason_codes": grant.reason_codes,
            "reasons": reasons,
            "summary": f"Risk is {r.risk.risk_level.value} ({r.risk.risk_score}/100): "
                       + "; ".join(reasons) + ".",
            "policy_id": grant.policy_id, "policy_version": grant.policy_version,
            "policy_hash": grant.policy_hash,
        }

    def allowed_actions(self, incident_id: str) -> list[dict]:
        r = self._record(incident_id)
        out: list[dict] = []
        for action_type in ALL_ACTION_TYPES:
            decision = evaluate_policy(action_type, r.risk, r.context, r.scene_at, self._config)
            out.append({"action_type": action_type.value, "decision": decision.decision.value,
                        "reason_codes": decision.reason_codes})
        return out

    def action_status(self, incident_id: str, action_id: str) -> dict:
        r = self._record(incident_id)
        action = r.actions.get(action_id)
        if action is None:
            raise NotFoundError("Action not found", {"action_id": action_id})
        execution = r.executions.get(action_id)
        decision = r.decisions.get(action_id)
        return {
            "action_id": action_id, "action_type": action.type.value,
            "status": action.status.value,
            "decision": decision.decision.value if decision else None,
            "execution": None if execution is None else {
                "execution_id": execution.execution_id, "status": execution.status.value,
                "provider": execution.provider.value,
            },
        }

    def timeline(self, incident_id: str) -> list[dict]:
        r = self._record(incident_id)
        return [{"action": e.action, "actor_type": e.actor_type.value, "actor_id": e.actor_id,
                 "decision": e.decision, "reason": e.reason,
                 "occurred_at": e.occurred_at.isoformat()} for e in r.timeline]

    # --- write surface (governed) ---------------------------------------------
    def propose(self, incident_id: str, action_type_value: str, actor_id: str,
                approval_ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS) -> dict:
        r = self._record(incident_id)
        try:
            action_type = SecurityActionType(action_type_value)
        except ValueError as exc:
            raise NotFoundError("Unknown action type", {"action_type": action_type_value}) from exc

        decision = evaluate_policy(action_type, r.risk, r.context, r.scene_at, self._config)
        action = SecurityAction(incident_id=incident_id, type=action_type,
                                provider=default_provider_for(action_type))
        r.actions[action.action_id] = action
        r.decisions[action.action_id] = decision
        self._audit(r, action=f"action.proposed:{action_type.value}", actor_id=actor_id,
                    actor_type=AuditActorType.HUMAN, decision=decision.decision.value,
                    reason=",".join(decision.reason_codes))

        result: dict = {"action_id": action.action_id, "decision": decision.decision.value,
                        "reason_codes": decision.reason_codes, "approval_id": None,
                        "executed": False}

        if decision.decision is PolicyDecisionType.ALLOW:
            action.status = ActionStatus.AUTHORIZED
            self._execute(r, action)
            result["executed"] = True
        elif decision.decision is PolicyDecisionType.REQUIRE_APPROVAL:
            role = self._config.approval_roles.get(action_type, "security")
            approval = ApprovalRequest(
                incident_id=incident_id, action_id=action.action_id, required_role=role,
                status=ApprovalStatus.PENDING,
                expires_at=_now() + timedelta(seconds=approval_ttl_seconds),
            )
            r.approvals[approval.approval_id] = approval
            r.proposed_by[approval.approval_id] = actor_id
            r.approval_action[approval.approval_id] = action.action_id
            r.incident.status = IncidentStatus.AWAITING_APPROVAL
            self._audit(r, action="approval.requested", actor_id=actor_id,
                        actor_type=AuditActorType.HUMAN, reason=f"requires role '{role}'")
            result["approval_id"] = approval.approval_id
            result["required_role"] = role
        else:  # DENY
            action.status = ActionStatus.REJECTED
        return result

    def approve(self, incident_id: str, approval_id: str, actor_id: str) -> dict:
        r = self._record(incident_id)
        approval = r.approvals.get(approval_id)
        if approval is None:
            raise NotFoundError("Approval not found", {"approval_id": approval_id})

        if approval.status is ApprovalStatus.APPROVED:
            return self._approved_result(r, approval, note="idempotent")  # duplicate is safe
        if approval.status is not ApprovalStatus.PENDING:
            raise ConflictError("Approval already resolved", {"status": approval.status.value})

        if approval.is_expired(_now()):
            approval.status = ApprovalStatus.EXPIRED
            self._audit(r, action="approval.expired", actor_id=actor_id, decision="EXPIRED")
            raise ApprovalExpiredError("Approval has expired")

        # Authority: the actor's RESOLVED role must match; claims in text are ignored.
        role = self._actors.role_for(actor_id)
        if role != approval.required_role:
            self._audit(r, action="approval.denied", actor_id=actor_id, decision="WRONG_ROLE",
                        reason=f"actor role '{role}' != required '{approval.required_role}'")
            raise WrongRoleError(
                f"Actor '{actor_id}' (role {role}) cannot approve; requires '{approval.required_role}'"
            )
        # Separation of duties: the proposer cannot approve their own action.
        if r.proposed_by.get(approval_id) == actor_id:
            self._audit(r, action="approval.denied", actor_id=actor_id, decision="SELF_APPROVAL")
            raise SelfApprovalError("The proposer cannot approve their own action")

        approval.status = ApprovalStatus.APPROVED
        approval.approved_by = actor_id
        approval.approved_at = _now()
        self._audit(r, action="approval.granted", actor_id=actor_id,
                    actor_type=AuditActorType.HUMAN, decision="APPROVED")

        action = r.actions[r.approval_action[approval_id]]
        action.status = ActionStatus.AUTHORIZED
        self._execute(r, action)          # exactly once
        r.incident.status = IncidentStatus.ACTIONED
        return self._approved_result(r, approval)

    def reject(self, incident_id: str, approval_id: str, actor_id: str) -> dict:
        r = self._record(incident_id)
        approval = r.approvals.get(approval_id)
        if approval is None:
            raise NotFoundError("Approval not found", {"approval_id": approval_id})
        if approval.status is ApprovalStatus.REJECTED:
            return {"approval_id": approval_id, "status": "REJECTED"}
        if approval.status is not ApprovalStatus.PENDING:
            raise ConflictError("Approval already resolved", {"status": approval.status.value})
        role = self._actors.role_for(actor_id)
        if role != approval.required_role:
            raise WrongRoleError(f"Actor '{actor_id}' cannot reject; requires '{approval.required_role}'")
        approval.status = ApprovalStatus.REJECTED
        action = r.actions[r.approval_action[approval_id]]
        action.status = ActionStatus.REJECTED
        self._audit(r, action="approval.rejected", actor_id=actor_id,
                    actor_type=AuditActorType.HUMAN, decision="REJECTED")
        return {"approval_id": approval_id, "status": "REJECTED"}

    # --- internals ------------------------------------------------------------
    def _execute(self, r: IncidentRecord, action: SecurityAction) -> ActionExecution:
        existing = r.executions.get(action.action_id)
        if existing is not None:
            return existing  # exactly-once guard
        execution = ActionExecution(
            incident_id=r.incident.incident_id, action_id=action.action_id,
            provider=action.provider or default_provider_for(action.type),
            status=ActionExecutionStatus.EXECUTED, idempotency_key=action.action_id,
            started_at=_now(), completed_at=_now(), result={"delivered": True},
        )
        r.executions[action.action_id] = execution
        self._audit(r, action=f"action.executed:{action.type.value}",
                    reason=f"provider {execution.provider.value}",
                    metadata={"execution_id": execution.execution_id})
        return execution

    def _approved_result(self, r: IncidentRecord, approval: ApprovalRequest, note: str = "") -> dict:
        action_id = r.approval_action[approval.approval_id]
        execution = r.executions.get(action_id)
        return {
            "approval_id": approval.approval_id, "status": approval.status.value,
            "action_id": action_id, "executed": execution is not None,
            "execution_id": execution.execution_id if execution else None, "note": note,
        }


_REASON_TEXT = {
    "BUILDING_CLOSED": "the building is closed",
    "OUTSIDE_BUSINESS_HOURS": "it is outside business hours",
    "NO_EXPECTED_VISITOR": "no visitor is expected",
    "NO_VERIFIED_VISITOR": "there is no verified visitor",
    "REPEATED_HUMAN_ACTIVITY": "repeated entrance activity occurred",
    "PROLONGED_ENTRANCE_ACTIVITY": "there was prolonged entrance activity",
    "NO_APPROVED_ACCESS_REQUEST": "no access request exists",
    "NO_VALID_CREDENTIAL": "no valid credential was presented",
    "RISK_TOO_HIGH": "the assessed risk is too high",
}


def _reason_sentences(risk_factors: list[str], reason_codes: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for code in list(risk_factors) + list(reason_codes):
        text = _REASON_TEXT.get(code)
        if text and text not in seen:
            seen[text] = None
    return list(seen)


# Process-wide singleton, seeded with the demo incident. MCP and REST share it.
officer = OfficerService()
DEMO_INCIDENT_ID = officer.seed_demo_incident()
