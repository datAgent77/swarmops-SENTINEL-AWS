"""VersionManager — immutable agent versions with governed activation + rollback.

Old versions are never overwritten; status flags which one is active. A high-risk
version stays PROPOSED until approved; a low-risk version is created APPROVED and
activated immediately. Rollback re-activates a prior version (history preserved).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Agent, AgentVersion
from app.domain.enums import RiskLevel, VersionStatus
from app.repositories import VersionRepository


def _bump_minor(version: str) -> str:
    try:
        major, minor = version.split(".", 1)
        return f"{int(major)}.{int(minor) + 1}"
    except (ValueError, AttributeError):
        return "1.1"


class VersionManager:
    def ensure_baseline(self, session: Session, agent: Agent) -> AgentVersion:
        repo = VersionRepository(session)
        active = repo.active_for_agent(agent.key)
        if active is not None:
            return active
        if repo.latest_for_agent(agent.key) is not None:
            # versions exist but none active (edge case) — leave as-is
            return repo.latest_for_agent(agent.key)
        return repo.create(
            agent_id=agent.id, agent_key=agent.key, version="1.0", parent_version=None,
            status=VersionStatus.ACTIVE, risk_level=RiskLevel.LOW,
            reason="Baseline version.", improvements=[], changes={},
            performance_delta={},
        )

    def propose(self, session: Session, agent: Agent, suggestions: list[dict], changes: dict,
                performance_delta: dict, risk: RiskLevel, reason: str) -> AgentVersion:
        repo = VersionRepository(session)
        self.ensure_baseline(session, agent)
        latest = repo.latest_for_agent(agent.key)
        active = repo.active_for_agent(agent.key)
        parent = active.version if active else "1.0"
        new_version = _bump_minor(latest.version if latest else "1.0")
        status = VersionStatus.PROPOSED if risk is RiskLevel.HIGH else VersionStatus.APPROVED
        row = repo.create(
            agent_id=agent.id, agent_key=agent.key, version=new_version, parent_version=parent,
            status=status, risk_level=risk, reason=reason, improvements=suggestions,
            changes=changes, performance_delta=performance_delta,
        )
        return row

    def approve(self, session: Session, version: AgentVersion) -> AgentVersion:
        VersionRepository(session).set_status(version, VersionStatus.APPROVED)
        return version

    def reject(self, session: Session, version: AgentVersion) -> AgentVersion:
        VersionRepository(session).set_status(version, VersionStatus.REJECTED)
        return version

    def activate(self, session: Session, version: AgentVersion) -> AgentVersion:
        repo = VersionRepository(session)
        current = repo.active_for_agent(version.agent_key)
        if current is not None and current.id != version.id:
            repo.set_status(current, VersionStatus.SUPERSEDED)
        repo.set_status(version, VersionStatus.ACTIVE, activated_at=utcnow())
        return version

    def rollback(self, session: Session, agent_key: str, target_version_id: uuid.UUID) -> AgentVersion:
        repo = VersionRepository(session)
        target = repo.get(target_version_id)
        if target is None or target.agent_key != agent_key:
            raise ValueError("target version not found for agent")
        # Never re-activate a governance-rejected or still-unapproved (proposed)
        # version by way of rollback — only versions that were legitimately live
        # or approved can be rolled back to.
        if target.status not in (VersionStatus.ACTIVE, VersionStatus.SUPERSEDED, VersionStatus.APPROVED):
            raise ValueError(f"cannot roll back to a {target.status.value} version")
        current = repo.active_for_agent(agent_key)
        if current is not None and current.id != target.id:
            repo.set_status(current, VersionStatus.SUPERSEDED)
        repo.set_status(target, VersionStatus.ACTIVE, activated_at=utcnow())
        return target
