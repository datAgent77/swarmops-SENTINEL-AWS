"""Sentinel domain enumerations.

Deliberately separate from ``app.domain.enums`` (mission/workforce vocabulary):
Sentinel speaks in locations, devices, events, incidents, observations, and
security actions. All are string-valued so they serialize cleanly across the
database, the API, and the UI.
"""

from __future__ import annotations

from enum import Enum


class DeviceType(str, Enum):
    DOORBELL = "DOORBELL"
    CAMERA = "CAMERA"
    MOTION_SENSOR = "MOTION_SENSOR"
    CONTACT_SENSOR = "CONTACT_SENSOR"
    OTHER = "OTHER"


class SecurityEventType(str, Enum):
    MOTION = "MOTION"
    DOORBELL_PRESS = "DOORBELL_PRESS"
    DEVICE_ONLINE = "DEVICE_ONLINE"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    OTHER = "OTHER"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    OBSERVING = "OBSERVING"
    ASSESSING = "ASSESSING"
    ESCALATED = "ESCALATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    ACTIONED = "ACTIONED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


# Incidents that accept no further transitions.
TERMINAL_INCIDENT_STATUSES = frozenset({IncidentStatus.RESOLVED, IncidentStatus.DISMISSED})


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyDecisionType(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class SecurityActionType(str, Enum):
    NOTIFY_OWNER = "NOTIFY_OWNER"
    REQUEST_LIVE_REVIEW = "REQUEST_LIVE_REVIEW"
    SEND_WARNING = "SEND_WARNING"
    NOTIFY_SECURITY = "NOTIFY_SECURITY"
    CREATE_INCIDENT_NOTE = "CREATE_INCIDENT_NOTE"
    GRANT_TEMPORARY_ACCESS = "GRANT_TEMPORARY_ACCESS"


class ActionProvider(str, Enum):
    """WHO carries out an action — kept separate from the action *intent*.

    Sentinel does not assume Ring can execute every action. Ring is eyes/ears;
    warnings, notifications, notes, and physical access are delivered by other
    providers (owner/security apps, an internal note store, a smart lock).
    """

    OWNER_APP = "OWNER_APP"
    SECURITY_TEAM = "SECURITY_TEAM"
    RING = "RING"
    SMART_LOCK = "SMART_LOCK"
    INTERNAL = "INTERNAL"


class ActionStatus(str, Enum):
    """Lifecycle of a recommended action (intent), independent of execution."""

    RECOMMENDED = "RECOMMENDED"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ActionExecutionStatus(str, Enum):
    """Lifecycle of a concrete execution attempt (exactly-once guarded)."""

    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class AuditActorType(str, Enum):
    SYSTEM = "SYSTEM"
    OFFICER = "OFFICER"   # the AI security officer (Sentinel)
    HUMAN = "HUMAN"
    DEVICE = "DEVICE"


# Default provider per action intent. Encodes that GRANT_TEMPORARY_ACCESS is a
# physical action a smart lock performs — never Ring, and never the AI itself.
DEFAULT_ACTION_PROVIDER: dict[SecurityActionType, ActionProvider] = {
    SecurityActionType.NOTIFY_OWNER: ActionProvider.OWNER_APP,
    SecurityActionType.REQUEST_LIVE_REVIEW: ActionProvider.OWNER_APP,
    SecurityActionType.SEND_WARNING: ActionProvider.SECURITY_TEAM,
    SecurityActionType.NOTIFY_SECURITY: ActionProvider.SECURITY_TEAM,
    SecurityActionType.CREATE_INCIDENT_NOTE: ActionProvider.INTERNAL,
    SecurityActionType.GRANT_TEMPORARY_ACCESS: ActionProvider.SMART_LOCK,
}


def default_provider_for(action_type: SecurityActionType) -> ActionProvider:
    return DEFAULT_ACTION_PROVIDER.get(action_type, ActionProvider.INTERNAL)
