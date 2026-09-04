"""Sentinel core domain models (strongly typed, Pydantic v2).

Design rules enforced here:

- **No authorization inside AI perception.** ``SecurityObservation`` forbids
  extra fields and explicitly rejects authz-shaped keys (allow_access, approved,
  unlock, …). Perception describes; it never decides.
- **Context is independent of perception.** ``BuildingContext`` carries facts
  (hours, visitors, access requests, credentials) that the deterministic layer
  uses — it is never inferred from model output.
- **Action intent is separate from action provider.** A ``SecurityAction`` names
  *what* to do; the provider names *who* carries it out (Ring cannot do everything).
- **Risk and decisions are reproducible.** Both are plain data recomputable from
  deterministic inputs (see ``app.sentinel.logic``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.sentinel.enums import (
    ActionExecutionStatus,
    ActionProvider,
    ActionStatus,
    ApprovalStatus,
    AuditActorType,
    DeviceType,
    IncidentStatus,
    PolicyDecisionType,
    RiskLevel,
    SecurityActionType,
    SecurityEventType,
    default_provider_for,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


# --- physical topology --------------------------------------------------------

class BusinessHours(BaseModel):
    """Deterministic opening schedule. ``building_open`` on the context remains the
    authoritative live state; this describes the nominal schedule."""

    opens: str = "09:00"          # "HH:MM", location-local
    closes: str = "18:00"
    open_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon=0

    def is_open_at(self, local_dt: datetime) -> bool:
        if local_dt.weekday() not in self.open_weekdays:
            return False
        minutes = local_dt.hour * 60 + local_dt.minute
        return self._to_min(self.opens) <= minutes < self._to_min(self.closes)

    @staticmethod
    def _to_min(hhmm: str) -> int:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)


class SecurityLocation(BaseModel):
    location_id: str = Field(default_factory=lambda: _new_id("loc"))
    name: str
    location_timezone: str = "UTC"
    business_hours: BusinessHours = Field(default_factory=BusinessHours)
    created_at: datetime = Field(default_factory=_utcnow)


class SecurityDevice(BaseModel):
    device_id: str = Field(default_factory=lambda: _new_id("dev"))
    location_id: str
    name: str
    type: DeviceType = DeviceType.OTHER
    capabilities: list[str] = Field(default_factory=list)
    online: bool = True


# --- events -------------------------------------------------------------------

class SecurityEvent(BaseModel):
    """A single sensor event. Many events may correlate into one incident.

    The base fields are provider-agnostic (P01). The optional ``provider_*`` and
    media fields (P02) carry a normalized Ring event without leaking raw payloads:
    only a hash of the raw metadata is retained, never secrets or media URLs.
    """

    event_id: str = Field(default_factory=lambda: _new_id("evt"))
    location_id: str
    device_id: str
    type: SecurityEventType = SecurityEventType.MOTION
    occurred_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Provenance/authenticity are proven upstream (e.g. Ring HMAC). Default False
    # so unverified events are never silently trusted.
    signature_verified: bool = False

    # --- P02: normalized provider (Ring) fields (all optional) ----------------
    provider: str | None = None                 # e.g. "ring"
    provider_event_id: str | None = None        # stable id for dedup (meta.request_id)
    provider_event_type: str | None = None      # e.g. "motion_detected"
    component_id: str | None = None             # multi-camera component
    motion_type: str | None = None              # e.g. "human" | "package" | "vehicle"
    media_reference: str | None = None          # opaque handle, never a sensitive URL
    raw_metadata_hash: str | None = None        # sha256 of the raw payload (audit, no PII)


# --- context (facts, never inferred from AI) ----------------------------------

class VisitorContext(BaseModel):
    visitor_id: str = Field(default_factory=lambda: _new_id("vis"))
    name: str | None = None
    expected_from: datetime | None = None
    expected_until: datetime | None = None
    verified: bool = False

    def is_valid_at(self, when: datetime) -> bool:
        if not self.verified:
            return False
        if self.expected_from and when < self.expected_from:
            return False
        if self.expected_until and when > self.expected_until:
            return False
        return True


class AccessRequest(BaseModel):
    """A pre-authorized access grant present in the building context (distinct from
    an ``ApprovalRequest``, which is a human sign-off on a Sentinel action)."""

    request_id: str = Field(default_factory=lambda: _new_id("acc"))
    subject: str | None = None
    approved: bool = False
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    approved_by: str | None = None

    def is_active_at(self, when: datetime) -> bool:
        if not self.approved:
            return False
        if self.valid_from and when < self.valid_from:
            return False
        if self.valid_until and when > self.valid_until:
            return False
        return True


class CredentialContext(BaseModel):
    presented: bool = False
    credential_id: str | None = None
    credential_type: str | None = None
    valid: bool = False


class BuildingContext(BaseModel):
    """Deterministic business context. ``building_open`` is authoritative."""

    business_hours: BusinessHours = Field(default_factory=BusinessHours)
    building_open: bool = False
    expected_visitors: list[VisitorContext] = Field(default_factory=list)
    active_access_requests: list[AccessRequest] = Field(default_factory=list)
    credential_state: CredentialContext = Field(default_factory=CredentialContext)
    delivery_expected: bool = False
    location_timezone: str = "UTC"


# --- AI perception (no authorization allowed) ---------------------------------

_PROHIBITED_OBSERVATION_FIELDS = frozenset(
    {"allow_access", "deny_access", "approved", "authorized", "unlock", "grant", "decision"}
)


class SecurityObservation(BaseModel):
    """AI perception ONLY. Describes the scene; carries no authority.

    ``extra="forbid"`` blocks unknown keys, and a pre-validator rejects
    authorization-shaped keys with an explicit error so a mislabeled model output
    can never smuggle a decision into perception.
    """

    model_config = ConfigDict(extra="forbid")

    person_present: bool = False
    vehicle_present: bool = False
    package_present: bool = False
    entrance_activity: bool = False
    prolonged_presence: bool = False
    repeated_activity: bool = False
    visibility: str = "clear"                 # e.g. clear | low | dark | obstructed
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    observation_codes: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="before")
    @classmethod
    def _reject_authorization(cls, data: Any) -> Any:
        if isinstance(data, dict):
            bad = _PROHIBITED_OBSERVATION_FIELDS & {str(k) for k in data}
            if bad:
                raise ValueError(
                    "SecurityObservation is perception only and must not carry "
                    f"authorization fields: {sorted(bad)}"
                )
        return data


# --- deterministic risk -------------------------------------------------------

class RiskAssessment(BaseModel):
    """Deterministic, recomputable from (observation, context). Not a decision."""

    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    risk_factors: list[str] = Field(default_factory=list)
    factor_scores: dict[str, int] = Field(default_factory=dict)
    policy_context: dict[str, Any] = Field(default_factory=dict)
    assessed_at: datetime = Field(default_factory=_utcnow)


# --- deterministic policy decision --------------------------------------------

class PolicyDecision(BaseModel):
    decision: PolicyDecisionType
    reason_codes: list[str] = Field(default_factory=list)
    policy_id: str
    policy_version: str
    policy_hash: str
    action_type: SecurityActionType | None = None
    evaluated_at: datetime = Field(default_factory=_utcnow)


# --- actions (intent vs provider vs execution) --------------------------------

class SecurityAction(BaseModel):
    action_id: str = Field(default_factory=lambda: _new_id("act"))
    incident_id: str
    type: SecurityActionType
    provider: ActionProvider | None = None
    status: ActionStatus = ActionStatus.RECOMMENDED
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _default_provider(self) -> SecurityAction:
        if self.provider is None:
            self.provider = default_provider_for(self.type)
        return self


class ApprovalRequest(BaseModel):
    approval_id: str = Field(default_factory=lambda: _new_id("appr"))
    incident_id: str
    action_id: str
    required_role: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or _utcnow()
        return self.expires_at is not None and now >= self.expires_at and self.status == ApprovalStatus.PENDING


class ActionExecution(BaseModel):
    execution_id: str = Field(default_factory=lambda: _new_id("exec"))
    incident_id: str
    action_id: str
    provider: ActionProvider
    status: ActionExecutionStatus = ActionExecutionStatus.PENDING
    # Exactly-once guard: two executions sharing a key are the same effect.
    idempotency_key: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AuditEvent(BaseModel):
    """Append-only audit record (domain shape; persisted in a later phase)."""

    audit_id: str = Field(default_factory=lambda: _new_id("aud"))
    incident_id: str | None = None
    actor_type: AuditActorType = AuditActorType.SYSTEM
    actor_id: str | None = None
    action: str
    decision: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=_utcnow)


# --- the security incident ----------------------------------------------------

class SecurityIncident(BaseModel):
    """A correlated case, not a single event. Holds the full officer arc."""

    incident_id: str = Field(default_factory=lambda: _new_id("inc"))
    location_id: str
    device_ids: list[str] = Field(default_factory=list)
    status: IncidentStatus = IncidentStatus.DETECTED
    severity: RiskLevel = RiskLevel.LOW
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    event_ids: list[str] = Field(default_factory=list)
    observation: SecurityObservation | None = None
    context: BuildingContext | None = None
    risk: RiskAssessment | None = None
    recommended_actions: list[SecurityAction] = Field(default_factory=list)
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    approval_requests: list[ApprovalRequest] = Field(default_factory=list)
    executions: list[ActionExecution] = Field(default_factory=list)
    resolution: str | None = None

    def transition(self, target: IncidentStatus) -> IncidentStatus:
        """Move to ``target`` if the lifecycle allows it, updating ``updated_at``."""
        from app.sentinel.lifecycle import assert_transition

        assert_transition(self.status, target)
        self.status = target
        self.updated_at = _utcnow()
        return self.status

    def add_event(self, event: SecurityEvent) -> None:
        if event.event_id not in self.event_ids:
            self.event_ids.append(event.event_id)
        if event.device_id not in self.device_ids:
            self.device_ids.append(event.device_id)
        self.updated_at = _utcnow()
