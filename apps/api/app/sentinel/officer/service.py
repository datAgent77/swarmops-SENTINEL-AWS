"""Authoritative officer service: incidents, actions, approvals, executions.

Every consequential step is governed and audited:
- ``propose`` evaluates the deterministic policy: ALLOW → execute exactly once;
  REQUIRE_APPROVAL → open a role-scoped, expiring ApprovalRequest; DENY → recorded.
- ``approve`` validates actor role, approval status, expiry, and separation of
  duties before execution.
- Execution runs through the idempotent, concurrency-safe ExecutionEngine, so
  repeated requests and concurrent approvals never duplicate an execution.
- No natural-language claim ("I am the admin", "skip approval") can bypass this;
  authority derives only from the resolved actor role and the policy engine.

The audit timeline is append-only; each record carries trace/idempotency/policy/
provider metadata where appropriate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.domain.errors import ConflictError, DomainError, NotFoundError
from app.sentinel.actions.engine import ExecutionEngine
from app.sentinel.actions.provider import DemoSecurityActionProvider, SecurityActionProvider
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
    trace_id: str
    actions: dict[str, SecurityAction] = field(default_factory=dict)
    decisions: dict[str, PolicyDecision] = field(default_factory=dict)   # action_id -> decision
    approvals: dict[str, ApprovalRequest] = field(default_factory=dict)
    proposed_by: dict[str, str] = field(default_factory=dict)            # approval_id -> actor
    approval_action: dict[str, str] = field(default_factory=dict)        # approval_id -> action_id
    action_approval: dict[str, str] = field(default_factory=dict)        # action_id -> approval_id
    executions: dict[str, ActionExecution] = field(default_factory=dict)  # action_id -> exec
    actions_by_key: dict[str, str] = field(default_factory=dict)         # idempotency_key -> action_id
    action_key: dict[str, str] = field(default_factory=dict)             # action_id -> idempotency_key
    timeline: list[AuditEvent] = field(default_factory=list)


class OfficerService:
    def __init__(self, config: PolicyConfig = DEFAULT_POLICY_CONFIG,
                 actors: ActorRegistry | None = None,
                 action_provider: SecurityActionProvider | None = None) -> None:
        self._config = config
        self._incidents: dict[str, IncidentRecord] = {}
        self._engine = ExecutionEngine(action_provider or DemoSecurityActionProvider())
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
        record = IncidentRecord(incident=incident, observation=observation, context=context,
                                risk=risk, scene_at=scene_at, trace_id=f"trace-{uuid.uuid4().hex[:16]}")
        self._incidents[incident_id] = record
        self._audit(record, action="incident_created", reason="entrance events correlated")
        self._audit(record, action="observation_generated",
                    reason=observation.summary,
                    metadata={"confidence": observation.confidence,
                              "codes": observation.observation_codes})
        self._audit(record, action="risk_calculated",
                    decision=risk.risk_level.value,
                    reason=f"{risk.risk_score}/100",
                    metadata={"risk_factors": risk.risk_factors})
        return incident_id

    def _record(self, incident_id: str) -> IncidentRecord:
        record = self._incidents.get(incident_id)
        if record is None:
            raise NotFoundError("Incident not found", {"incident_id": incident_id})
        return record

    def _audit(self, record: IncidentRecord, *, action: str, reason: str | None = None,
               actor_id: str | None = None, actor_type: AuditActorType = AuditActorType.SYSTEM,
               decision: str | None = None, metadata: dict | None = None) -> None:
        meta = {"trace_id": record.trace_id}
        if metadata:
            meta.update(metadata)
        record.timeline.append(AuditEvent(
            incident_id=record.incident.incident_id, actor_type=actor_type, actor_id=actor_id,
            action=action, decision=decision, reason=reason, metadata=meta,
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
            "trace_id": r.trace_id,
            "provider_mode": self._engine.mode().value,
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
            "idempotency_key": r.action_key.get(action_id),
            "execution": None if execution is None else {
                "execution_id": execution.execution_id, "status": execution.status.value,
                "provider": execution.provider.value if execution.provider else None,
            },
        }

    def timeline(self, incident_id: str) -> list[dict]:
        r = self._record(incident_id)
        return [{"action": e.action, "actor_type": e.actor_type.value, "actor_id": e.actor_id,
                 "decision": e.decision, "reason": e.reason, "metadata": e.metadata,
                 "occurred_at": e.occurred_at.isoformat()} for e in r.timeline]

    # --- write surface (governed) ---------------------------------------------
    def propose(self, incident_id: str, action_type_value: str, actor_id: str,
                action_request_id: str | None = None,
                approval_ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS) -> dict:
        r = self._record(incident_id)
        try:
            action_type = SecurityActionType(action_type_value)
        except ValueError as exc:
            raise NotFoundError("Unknown action type", {"action_type": action_type_value}) from exc

        # Stable idempotency key: incident + action_type + request id (or a fresh one).
        request_id = action_request_id or f"auto-{uuid.uuid4().hex[:12]}"
        idem_key = f"{incident_id}:{action_type.value}:{request_id}"

        # Idempotent propose: the exact same logical request maps to the same action.
        if idem_key in r.actions_by_key:
            return self._idempotent_propose(r, idem_key, actor_id)

        decision = evaluate_policy(action_type, r.risk, r.context, r.scene_at, self._config)
        action = SecurityAction(incident_id=incident_id, type=action_type,
                                provider=default_provider_for(action_type))
        r.actions[action.action_id] = action
        r.decisions[action.action_id] = decision
        r.actions_by_key[idem_key] = action.action_id
        r.action_key[action.action_id] = idem_key

        self._audit(r, action="policy_evaluated", actor_id=actor_id, actor_type=AuditActorType.HUMAN,
                    decision=decision.decision.value,
                    metadata=self._policy_meta(decision, action.action_id, idem_key))
        self._audit(r, action="action_proposed", actor_id=actor_id, actor_type=AuditActorType.HUMAN,
                    reason=action_type.value, metadata={"action_id": action.action_id,
                                                        "idempotency_key": idem_key})

        result: dict = {"action_id": action.action_id, "decision": decision.decision.value,
                        "reason_codes": decision.reason_codes, "approval_id": None,
                        "executed": False, "duplicate_prevented": False,
                        "idempotency_key": idem_key}

        if decision.decision is PolicyDecisionType.ALLOW:
            action.status = ActionStatus.AUTHORIZED
            execution, prevented = self._run_execution(r, action)
            result["executed"] = execution.status is ActionExecutionStatus.EXECUTED
            result["execution_id"] = execution.execution_id
            result["duplicate_prevented"] = prevented
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
            r.action_approval[action.action_id] = approval.approval_id
            r.incident.status = IncidentStatus.AWAITING_APPROVAL
            self._audit(r, action="approval_requested", actor_id=actor_id, actor_type=AuditActorType.HUMAN,
                        reason=f"requires role '{role}'",
                        metadata={"approval_id": approval.approval_id, "action_id": action.action_id})
            result["approval_id"] = approval.approval_id
            result["required_role"] = role
        else:  # DENY
            action.status = ActionStatus.REJECTED
            self._audit(r, action="action_denied", actor_id=actor_id, actor_type=AuditActorType.HUMAN,
                        decision="DENY", reason=",".join(decision.reason_codes),
                        metadata={"action_id": action.action_id,
                                  "reason_codes": decision.reason_codes})
        return result

    def _idempotent_propose(self, r: IncidentRecord, idem_key: str, actor_id: str) -> dict:
        action_id = r.actions_by_key[idem_key]
        decision = r.decisions[action_id]
        execution = r.executions.get(action_id)
        approval_id = r.action_approval.get(action_id)
        executed = execution is not None and execution.status is ActionExecutionStatus.EXECUTED
        if executed:
            self._audit(r, action="duplicate_execution_prevented", actor_id=actor_id,
                        actor_type=AuditActorType.HUMAN, reason="repeated request",
                        metadata={"action_id": action_id, "idempotency_key": idem_key,
                                  "execution_id": execution.execution_id})
        return {
            "action_id": action_id, "decision": decision.decision.value,
            "reason_codes": decision.reason_codes, "approval_id": approval_id,
            "executed": executed, "duplicate_prevented": executed, "idempotency_key": idem_key,
            "execution_id": execution.execution_id if execution else None,
        }

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
            self._audit(r, action="approval_denied", actor_id=actor_id, decision="EXPIRED",
                        metadata={"approval_id": approval_id})
            raise ApprovalExpiredError("Approval has expired")

        # Authority: the actor's RESOLVED role must match; claims in text are ignored.
        role = self._actors.role_for(actor_id)
        if role != approval.required_role:
            self._audit(r, action="approval_denied", actor_id=actor_id, decision="WRONG_ROLE",
                        reason=f"actor role '{role}' != required '{approval.required_role}'",
                        metadata={"approval_id": approval_id})
            raise WrongRoleError(
                f"Actor '{actor_id}' (role {role}) cannot approve; requires '{approval.required_role}'"
            )
        # Separation of duties: the proposer cannot approve their own action.
        if r.proposed_by.get(approval_id) == actor_id:
            self._audit(r, action="approval_denied", actor_id=actor_id, decision="SELF_APPROVAL",
                        metadata={"approval_id": approval_id})
            raise SelfApprovalError("The proposer cannot approve their own action")

        approval.status = ApprovalStatus.APPROVED
        approval.approved_by = actor_id
        approval.approved_at = _now()
        self._audit(r, action="approval_granted", actor_id=actor_id, actor_type=AuditActorType.HUMAN,
                    decision="APPROVED", metadata={"approval_id": approval_id})

        action = r.actions[r.approval_action[approval_id]]
        action.status = ActionStatus.AUTHORIZED
        self._run_execution(r, action, actor_id=actor_id)   # idempotent + concurrency-safe
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
        self._audit(r, action="approval_rejected", actor_id=actor_id, actor_type=AuditActorType.HUMAN,
                    decision="REJECTED", metadata={"approval_id": approval_id})
        return {"approval_id": approval_id, "status": "REJECTED"}

    def resolve(self, incident_id: str, actor_id: str, note: str = "") -> dict:
        r = self._record(incident_id)
        r.incident.transition(IncidentStatus.RESOLVED)
        r.incident.resolution = note or "resolved by officer"
        self._audit(r, action="incident_resolved", actor_id=actor_id, actor_type=AuditActorType.HUMAN,
                    reason=r.incident.resolution)
        return {"incident_id": incident_id, "status": r.incident.status.value}

    # --- winner proof: same request twice → duplicate prevented ---------------
    def winner_proof(self, actor_owner: str = "owner-alex", actor_officer: str = "officer-sam") -> dict:
        iid = self.seed_demo_incident(f"inc-proof-{uuid.uuid4().hex[:8]}")
        request_id = "warn-req-1"
        first = self.propose(iid, "SEND_WARNING", actor_owner, action_request_id=request_id)
        approved = self.approve(iid, first["approval_id"], actor_officer)
        # Send the EXACT same request again.
        second = self.propose(iid, "SEND_WARNING", actor_owner, action_request_id=request_id)
        executed_count = sum(
            1 for e in self._record(iid).executions.values()
            if e.status is ActionExecutionStatus.EXECUTED
        )
        return {
            "incident_id": iid,
            "first_execution_id": approved.get("execution_id"),
            "second_execution_id": second.get("execution_id"),
            "duplicate_prevented": second.get("duplicate_prevented"),
            "executed_count": executed_count,
            "timeline": self.timeline(iid),
        }

    # --- internals ------------------------------------------------------------
    def _run_execution(self, r: IncidentRecord, action: SecurityAction,
                       actor_id: str | None = None) -> tuple[ActionExecution, bool]:
        key = r.action_key[action.action_id]
        channel = action.provider or default_provider_for(action.type)
        self._audit(r, action="execution_started", actor_id=actor_id,
                    reason=action.type.value,
                    metadata={"action_id": action.action_id, "idempotency_key": key,
                              "provider": channel.value, "provider_mode": self._engine.mode().value})
        execution, prevented = self._engine.execute(
            idempotency_key=key, incident_id=r.incident.incident_id, action_id=action.action_id,
            action_type=action.type, channel=channel,
        )
        r.executions[action.action_id] = execution
        meta = {"action_id": action.action_id, "idempotency_key": key,
                "execution_id": execution.execution_id, "provider": channel.value,
                "provider_mode": self._engine.mode().value}
        if prevented:
            self._audit(r, action="duplicate_execution_prevented", actor_id=actor_id, metadata=meta)
        elif execution.status is ActionExecutionStatus.EXECUTED:
            self._audit(r, action="execution_completed", actor_id=actor_id, metadata=meta)
        else:
            self._audit(r, action="execution_failed", actor_id=actor_id,
                        reason=execution.error, metadata=meta)
        return execution, prevented

    def _policy_meta(self, decision: PolicyDecision, action_id: str, idem_key: str) -> dict:
        return {"action_id": action_id, "idempotency_key": idem_key,
                "reason_codes": decision.reason_codes, "policy_id": decision.policy_id,
                "policy_version": decision.policy_version, "policy_hash": decision.policy_hash}

    def _approved_result(self, r: IncidentRecord, approval: ApprovalRequest, note: str = "") -> dict:
        action_id = r.approval_action[approval.approval_id]
        execution = r.executions.get(action_id)
        return {
            "approval_id": approval.approval_id, "status": approval.status.value,
            "action_id": action_id,
            "executed": execution is not None and execution.status is ActionExecutionStatus.EXECUTED,
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
