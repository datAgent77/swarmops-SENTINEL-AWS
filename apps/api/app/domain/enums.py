"""Shared enums used by both the ORM models and the API schemas.

Keeping these in one place ensures the database, the governance engine, the
orchestrator state machine, and the API all speak the same vocabulary.
"""

from __future__ import annotations

from enum import Enum


class MissionStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    ASSIGNED = "assigned"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    VALIDATING = "validating"
    COMPLETED = "completed"
    # terminal / off-happy-path
    BLOCKED = "blocked"
    REJECTED = "rejected"
    FAILED = "failed"


TERMINAL_MISSION_STATUSES = frozenset(
    {MissionStatus.COMPLETED, MissionStatus.REJECTED, MissionStatus.FAILED, MissionStatus.BLOCKED}
)


class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    QUARANTINED = "quarantined"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


class DecisionResult(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    APPROVAL_REQUIRED = "approval_required"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Environment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"


class VersionStatus(str, Enum):
    PROPOSED = "proposed"        # awaiting governance/human approval (high-risk)
    APPROVED = "approved"        # approved but not yet the active version
    REJECTED = "rejected"
    ACTIVE = "active"            # currently the agent's live version
    SUPERSEDED = "superseded"    # was active, replaced by a newer version


class RiskLevel(str, Enum):
    LOW = "low"                  # may auto-approve
    HIGH = "high"                # requires governance / human approval
