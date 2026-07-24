"""EvolutionService — orchestrates evaluation, improvement, versioning, approval.

Runs after a mission completes: evaluates each agent, proposes improvements,
auto-activates low-risk versions, and leaves high-risk versions PROPOSED for
governance approval. Emits evolution events into the mission timeline so the
whole loop is observable. All logic is deterministic and reversible.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.agents.personas import PERSONAS
from app.db.models import CostRecord, GovernanceDecision
from app.db.session import session_scope
from app.domain.enums import RiskLevel, VersionStatus
from app.domain.errors import ConflictError, NotFoundError
from app.evolution.evaluator import PerformanceEvaluator
from app.evolution.improvement import ImprovementEngine
from app.evolution.policy import EvolutionPolicy
from app.evolution.schemas import (
    AgentVersionRead,
    EvolutionAgentCard,
    MissionSummary,
    PerformanceReportRead,
    VersionComparison,
)
from app.evolution.versioning import VersionManager
from app.orchestration.coordinator import coordinator
from app.repositories import (
    AgentRepository,
    EventRepository,
    MissionRepository,
    PerformanceRepository,
    TaskRepository,
    VersionRepository,
)

log = logging.getLogger("swarmops.evolution")


def _agent_name(key: str) -> str:
    persona = PERSONAS.get(key)
    return persona.display_name if persona else key


class EvolutionService:
    def __init__(self) -> None:
        self.evaluator = PerformanceEvaluator()
        self.improver = ImprovementEngine()
        self.policy = EvolutionPolicy()
        self.versions = VersionManager()

    # --- run after a mission completes -------------------------------------
    def evaluate_mission(self, mission_id: uuid.UUID) -> None:
        seqs: list[int] = []
        with session_scope() as session:
            mission = MissionRepository(session).get(mission_id)
            if mission is None:
                return
            agents = AgentRepository(session).list_for_org(mission.organization_id)
            events = EventRepository(session).list_for_mission(mission_id)
            decisions = list(session.scalars(
                select(GovernanceDecision).where(GovernanceDecision.mission_id == mission_id)
            ))
            tasks = TaskRepository(session).list_for_mission(mission_id)
            all_costs = list(session.scalars(
                select(CostRecord).where(CostRecord.mission_id == mission_id)
            ))
            perf_repo = PerformanceRepository(session)
            events_repo = EventRepository(session)

            def emit(type_: str, actor: str, message: str, payload: dict) -> None:
                ev = events_repo.append(mission_id, type_, actor, message, payload)
                seqs.append(ev.seq)

            for agent in agents:
                # Each agent is isolated in its own SAVEPOINT so one agent's
                # failure can never poison the transaction and zero out the rest.
                # Phase 1 (score + report) must persist even if Phase 2 fails.
                try:
                    with session.begin_nested():
                        self.versions.ensure_baseline(session, agent)
                        ev = self.evaluator.evaluate(mission, agent, events, decisions, tasks, all_costs)
                        perf_repo.create(mission_id, agent.id, agent.key, ev.score, ev.metrics, ev.weaknesses)
                        emit("agent.evaluation.completed", agent.key,
                             f"{_agent_name(agent.key)} scored {ev.score:.0f}/100.",
                             {"score": ev.score, "weaknesses": [w["code"] for w in ev.weaknesses]})
                except Exception as exc:  # noqa: BLE001 — never let one agent zero out the rest
                    log.warning("evolution: evaluation skipped for %s: %s", agent.key, exc)
                    continue

                if not ev.weaknesses:
                    continue
                suggestions = self.improver.suggest(ev.weaknesses)
                if not suggestions:
                    continue
                # Phase 2 (improvement + versioning) is best-effort; the report is already saved.
                try:
                    with session.begin_nested():
                        changes = self.improver.merge_changes(suggestions)
                        delta = self.improver.projected_delta(ev.score, suggestions)
                        risk = self.policy.classify_many([s["category"] for s in suggestions])
                        reason = "; ".join(s["suggestion"] for s in suggestions)
                        version = self.versions.propose(session, agent, suggestions, changes, delta, risk, reason)
                        emit("agent.improvement.proposed", agent.key,
                             f"{_agent_name(agent.key)}: {suggestions[0]['suggestion']}",
                             {"version": version.version, "risk": risk.value, "suggestions": suggestions})
                        emit("agent.version.created", agent.key,
                             f"{_agent_name(agent.key)} v{version.version} created ({risk.value} risk).",
                             {"version": version.version, "risk": risk.value, "version_id": str(version.id)})
                        if risk is RiskLevel.LOW:
                            self.versions.activate(session, version)
                            emit("agent.version.approved", agent.key,
                                 f"{_agent_name(agent.key)} v{version.version} auto-approved (low risk).",
                                 {"version": version.version, "version_id": str(version.id)})
                            emit("agent.version.activated", agent.key,
                                 f"{_agent_name(agent.key)} upgraded to v{version.version}.",
                                 {"version": version.version, "version_id": str(version.id)})
                        else:
                            emit("agent.version.pending_approval", agent.key,
                                 f"{_agent_name(agent.key)} v{version.version} requires governance approval.",
                                 {"version": version.version, "version_id": str(version.id), "risk": risk.value})
                except Exception as exc:  # noqa: BLE001 — improvement is best-effort; score already saved
                    log.warning("evolution: improvement skipped for %s: %s", agent.key, exc)
        for seq in seqs:
            coordinator.publish(str(mission_id), seq)

    # --- approval / rollback (governed; followed by a dashboard refetch) ---
    def approve_version(self, version_id: uuid.UUID) -> AgentVersionRead:
        with session_scope() as session:
            version = VersionRepository(session).get(version_id)
            if version is None:
                raise NotFoundError("Version not found", {"version_id": str(version_id)})
            if version.status is not VersionStatus.PROPOSED:
                raise ConflictError("Version is not pending approval", {"status": version.status.value})
            self.versions.approve(session, version)
            self.versions.activate(session, version)
            mid = _recent_mission(session, version)
            for type_, msg in (("agent.version.approved", "approved by governance"),
                               ("agent.version.activated", f"upgraded to v{version.version}")):
                EventRepository(session).append(
                    mid, type_, version.agent_key, f"{_agent_name(version.agent_key)} {msg}.",
                    {"version": version.version, "version_id": str(version.id)})
            return AgentVersionRead.model_validate(version)

    def reject_version(self, version_id: uuid.UUID) -> AgentVersionRead:
        with session_scope() as session:
            version = VersionRepository(session).get(version_id)
            if version is None:
                raise NotFoundError("Version not found", {"version_id": str(version_id)})
            if version.status is not VersionStatus.PROPOSED:
                raise ConflictError("Version is not pending approval", {"status": version.status.value})
            self.versions.reject(session, version)
            EventRepository(session).append(
                _recent_mission(session, version), "agent.version.rejected", version.agent_key,
                f"{_agent_name(version.agent_key)} v{version.version} rejected.",
                {"version": version.version, "version_id": str(version.id)})
            return AgentVersionRead.model_validate(version)

    def rollback(self, agent_key: str, version_id: uuid.UUID) -> AgentVersionRead:
        with session_scope() as session:
            target = self.versions.rollback(session, agent_key, version_id)
            result = AgentVersionRead.model_validate(target)
        return result

    # --- reads -------------------------------------------------------------
    def get_dashboard(self, session) -> list[EvolutionAgentCard]:
        perf = PerformanceRepository(session)
        vers = VersionRepository(session)
        cards: list[EvolutionAgentCard] = []
        for key in PERSONAS:
            history = perf.history_for_agent(key)
            latest = history[-1] if history else None
            score = float(latest.score) if latest else 0.0
            trend = "flat"
            if len(history) >= 2:
                diff = float(history[-1].score) - float(history[-2].score)
                trend = "up" if diff > 0.5 else ("down" if diff < -0.5 else "flat")
            active = vers.active_for_agent(key)
            latest_ver = vers.latest_for_agent(key)
            improvement_score = 0.0
            if latest_ver and latest_ver.performance_delta:
                improvement_score = float(latest_ver.performance_delta.get("score_gain", 0.0))
            pending = next((v for v in vers.list_for_agent(key) if v.status == VersionStatus.PROPOSED), None)
            cards.append(EvolutionAgentCard(
                agent_key=key, name=_agent_name(key),
                current_version=(active.version if active else "1.0"),
                performance_score=round(score, 1),
                improvement_score=round(improvement_score, 1),
                trend=trend,
                pending_version=AgentVersionRead.model_validate(pending) if pending else None,
            ))
        return cards

    def get_mission_summary(self, session, mission_id: uuid.UUID) -> MissionSummary:
        if MissionRepository(session).get(mission_id) is None:
            raise NotFoundError("Mission not found", {"mission_id": str(mission_id)})
        reports = PerformanceRepository(session).list_for_mission(mission_id)
        if not reports:
            return MissionSummary(mission_id=mission_id, reports=[])
        gains = {}
        for r in reports:
            suggestions = self.improver.suggest(r.weaknesses)
            gains[r.agent_key] = self.improver.projected_delta(float(r.score), suggestions)["score_gain"]
        top = max(reports, key=lambda r: float(r.score))
        highest_cost = max(reports, key=lambda r: float(r.metrics.get("estimated_cost", 0)))
        highest_risk = max(reports, key=lambda r: float(r.metrics.get("blocked_actions", 0)) * 2
                           + float(r.metrics.get("approval_count", 0)))
        most_improved = max(reports, key=lambda r: gains.get(r.agent_key, 0.0))
        lowest = min(reports, key=lambda r: float(r.score))
        return MissionSummary(
            mission_id=mission_id,
            top_performer=_agent_name(top.agent_key),
            most_improved=_agent_name(most_improved.agent_key),
            highest_cost_agent=_agent_name(highest_cost.agent_key),
            highest_risk_agent=_agent_name(highest_risk.agent_key),
            biggest_opportunity=f"{_agent_name(lowest.agent_key)}: "
                                f"{(lowest.weaknesses[0]['label'] if lowest.weaknesses else 'well-rounded')}",
            reports=[PerformanceReportRead.model_validate(r) for r in reports],
        )

    def get_comparison(self, session, version_id: uuid.UUID) -> VersionComparison:
        version = VersionRepository(session).get(version_id)
        if version is None:
            raise NotFoundError("Version not found", {"version_id": str(version_id)})
        delta = version.performance_delta or {}
        metrics = [{"label": "Performance score",
                    "before": delta.get("score_before"), "after": delta.get("score_after")}]
        for key, change in (delta.get("metric_projections") or {}).items():
            metrics.append({"label": key, "before": None, "after": f"{'+' if change >= 0 else ''}{change}"})
        return VersionComparison(agent_key=version.agent_key, from_version=version.parent_version or "1.0",
                                 to_version=version.version, metrics=metrics)


def _recent_mission(session, version) -> uuid.UUID:
    """Attach an evolution approval event to the most recent mission's timeline."""
    latest = MissionRepository(session).list()
    return latest[0].id if latest else version.agent_id


evolution_service = EvolutionService()
