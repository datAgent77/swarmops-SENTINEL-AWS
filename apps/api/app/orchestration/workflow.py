"""Persistent, deterministic mission orchestrator.

Drives the demo workflow as an explicit state machine, persisting every mission,
task, event, governance decision, approval, and cost record to PostgreSQL. The
approval step genuinely pauses the coroutine (awaiting an asyncio event) without
blocking the FastAPI event loop, and resumes only when a real approval API call
arrives. Governance outcomes come from the deterministic engine and are never
altered here.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from app.agents.agent import AgentResult, AgentRunner
from app.agents.memory import MissionMemory
from app.agents.personas import PERSONAS
from app.config import get_settings
from app.db.session import session_scope
from app.domain.enums import (
    AgentStatus,
    DecisionResult,
    Environment,
    MissionStatus,
    TaskStatus,
)
from app.governance.engine import ActionRequest, GovernanceEngine
from app.orchestration.coordinator import coordinator
from app.orchestration.state_machine import assert_transition
from app.providers.comms.base import CommsProvider
from app.providers.comms.factory import get_comms
from app.providers.context.base import ContextProvider
from app.providers.context.factory import get_context
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import get_provider
from app.providers.llm.pricing import estimate_cost
from app.providers.publish.base import PublishProvider
from app.providers.publish.factory import get_publisher
from app.repositories import (
    AgentRepository,
    ApprovalRepository,
    CostRepository,
    EventRepository,
    GovernanceDecisionRepository,
    MissionRepository,
    TaskRepository,
)

DEPLOY_ENVIRONMENT = Environment.PRODUCTION.value


class MissionOrchestrator:
    def __init__(self, step_delay: float | None = None, governance: GovernanceEngine | None = None,
                 provider: LLMProvider | None = None, comms: CommsProvider | None = None,
                 context: ContextProvider | None = None, publisher: PublishProvider | None = None) -> None:
        self.governance = governance or GovernanceEngine()
        self.step_delay = get_settings().demo_event_delay_seconds if step_delay is None else step_delay
        # LLM access is ONLY through the provider abstraction (Gemini or Mock,
        # wrapped with timeout/retry/fallback). Governance never uses the LLM.
        self.provider = provider or get_provider()
        self.runner = AgentRunner(self.provider)
        # Sponsor: inter-agent conversation is mirrored to a Band room when a key
        # is configured; a local no-op otherwise. The DB audit trail is unchanged
        # and remains the source of truth; comms is a best-effort side channel.
        self.comms = comms or get_comms()
        self._rooms: dict[uuid.UUID, str] = {}
        # Sponsor: agents retrieve/ingest verified context through Senso when a key
        # is configured; a local no-op otherwise. Mission memory stays the working
        # store — this augments it, it does not replace it.
        self.context = context or get_context()
        # Real action: publish the finished mission report to cited.md (the agentic
        # web) when a key is configured; otherwise the report is served locally.
        self.publisher = publisher or get_publisher()

    async def _mirror_message(self, mission_id: uuid.UUID, sender: str, content: str) -> None:
        room = self._rooms.get(mission_id)
        if room:
            await self.comms.send_message(room, sender, content)

    async def _mirror_event(self, mission_id: uuid.UUID, sender: str, kind: str, content: str) -> None:
        room = self._rooms.get(mission_id)
        if room:
            await self.comms.post_event(room, sender, kind, content)

    async def _pace(self) -> None:
        if self.step_delay:
            await asyncio.sleep(self.step_delay)

    # --- persistence helpers (each owns a short transaction) ----------------
    def _emit(self, mission_id: uuid.UUID, type_: str, actor: str, message: str, payload: dict | None = None) -> int:
        with session_scope() as session:
            event = EventRepository(session).append(mission_id, type_, actor, message, payload)
            seq = event.seq
        coordinator.publish(str(mission_id), seq)  # wake SSE after commit
        return seq

    def _transition(self, mission_id: uuid.UUID, target: MissionStatus) -> None:
        with session_scope() as session:
            mission = MissionRepository(session).get(mission_id)
            assert_transition(mission.status, target)
            MissionRepository(session).set_status(mission, target)

    def _set_agent(self, mission_id: uuid.UUID, org_id: uuid.UUID, key: str, status: AgentStatus) -> None:
        with session_scope() as session:
            agent = AgentRepository(session).get_by_key(org_id, key)
            if agent is not None:
                AgentRepository(session).set_status(agent, status)

    def _cost(self, mission_id: uuid.UUID, org_id: uuid.UUID, agent_key: str, description: str,
              amount: Decimal) -> None:
        with session_scope() as session:
            agent = AgentRepository(session).get_by_key(org_id, agent_key)
            CostRepository(session).create(mission_id, description, amount, agent.id if agent else None)
        self._emit(mission_id, "cost.recorded", "finance", f"{description}: ${amount:.2f}",
                   {"amount_usd": float(amount), "description": description})

    # --- main workflow ------------------------------------------------------
    async def run(self, mission_id: uuid.UUID) -> None:
        try:
            await self._run(mission_id)
        except Exception as exc:  # noqa: BLE001 — surface failures as an auditable event, never swallow
            self._emit(mission_id, "mission.failed", "system", f"Mission failed: {exc}")
            with session_scope() as session:
                mission = MissionRepository(session).get(mission_id)
                if mission and mission.status not in {
                    MissionStatus.COMPLETED, MissionStatus.REJECTED, MissionStatus.FAILED
                }:
                    MissionRepository(session).set_status(mission, MissionStatus.FAILED)
            raise

    async def _agent_step(self, mission_id: uuid.UUID, org_id: uuid.UUID, key: str,
                          memory: MissionMemory, instruction: str = "",
                          extra_context: dict | None = None) -> AgentResult:
        """Run one AI agent: think → reason → decide, updating shared memory and
        emitting reasoning/conversation events + token/cost telemetry. Tool
        requests are returned for the caller to route through governance."""
        persona = PERSONAS[key]
        self._set_agent(mission_id, org_id, key, AgentStatus.WORKING)
        await self._pace()
        self._emit(mission_id, "agent.thinking", key, f"{persona.display_name} Agent is thinking…",
                   {"phase": "thinking"})

        # Pull verified context from the context layer (Senso) into working memory.
        memory.context_hint = await self.context.query(instruction or memory.objective)

        result = await self.runner.run(persona, memory, instruction, extra_context)

        # Shared memory is passed between agents (not prompt concatenation).
        memory.record_output(key, result.output_dict)
        memory.add_reasoning(key, result.reasoning_summary)
        memory.add_message(key, result.message)
        # Contribute this agent's output back to the shared context layer.
        await self.context.ingest(f"{persona.display_name}: {result.message}", source=key)
        memory.add_risks(result.output_dict.get("risks", []) or [])
        if key == "pm":
            memory.add_tasks(result.output_dict.get("tasks", []) or [])

        usage = result.response.usage
        cost = estimate_cost(result.response.model, usage)
        self._emit(mission_id, "agent.reasoning", key, result.reasoning_summary,
                   {"phase": "reasoning", "provider": result.response.provider,
                    "model": result.response.model, "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens, "cost_usd": float(cost),
                    "latency_ms": result.response.latency_ms})
        self._emit(mission_id, "agent.message", key, result.message, {"conversation": True})
        await self._mirror_message(mission_id, persona.display_name, result.message)

        with session_scope() as session:
            agent = AgentRepository(session).get_by_key(org_id, key)
            CostRepository(session).create(
                mission_id, f"LLM {persona.display_name} ({result.response.provider})",
                cost, agent.id if agent else None)
        return result

    async def _run(self, mission_id: uuid.UUID) -> None:
        with session_scope() as session:
            mission = MissionRepository(session).get(mission_id)
            org_id = mission.organization_id
            budget = mission.budget_usd
            objective = mission.objective

        memory = MissionMemory(objective=objective, mission_summary=f"Deliver: {objective}")
        self._emit(mission_id, "mission.started", "system", "Mission accepted. Assembling the AI workforce.")
        sponsors = get_settings().active_sponsors()
        if sponsors:
            self._emit(mission_id, "sponsors.active", "system",
                       f"Sponsor tools active: {', '.join(sponsors)}.",
                       {"sponsors": sponsors})
        # Open (or reuse) a Band room for this mission's inter-agent conversation.
        self._rooms[mission_id] = await self.comms.ensure_room(
            str(mission_id), f"SwarmOps · {objective[:60]}")

        # CEO — strategy -> planning
        self._transition(mission_id, MissionStatus.PLANNING)
        ceo = await self._agent_step(mission_id, org_id, "ceo", memory,
                                     "Analyze the mission and set strategy and priorities.")
        self._emit(mission_id, "plan.created", "ceo", "CEO Agent produced a strategy and plan.",
                   {"decision": ceo.output_dict})
        self._set_agent(mission_id, org_id, "ceo", AgentStatus.COMPLETED)
        memory.record_handoff("ceo", "pm")

        # PM — decomposition -> tasks -> assigned
        pm = await self._agent_step(mission_id, org_id, "pm", memory,
                                    "Decompose the mission into concrete tasks with dependencies.")
        titles = pm.output_dict.get("tasks", []) or []
        self._create_tasks_from(mission_id, org_id, titles)
        self._emit(mission_id, "tasks.created", "pm",
                   f"Product Manager Agent created {len(titles) or 1} mission tasks.",
                   {"decision": pm.output_dict})
        self._set_agent(mission_id, org_id, "pm", AgentStatus.COMPLETED)
        self._transition(mission_id, MissionStatus.ASSIGNED)
        memory.record_handoff("pm", "developer")

        # Finance — budget review
        fin = await self._agent_step(mission_id, org_id, "finance", memory,
                                     "Assess the mission budget and cost.")
        self._emit(mission_id, "budget.reviewed", "finance",
                   f"Finance Agent reviewed the budget (${budget:.2f}): {fin.output_dict.get('budgetStatus')}.",
                   {"budget_usd": float(budget), "decision": fin.output_dict})
        self._set_agent(mission_id, org_id, "finance", AgentStatus.COMPLETED)

        # Developer — implementation -> running; tool requests go through governance
        self._transition(mission_id, MissionStatus.RUNNING)
        self._set_task_status(mission_id, "developer", TaskStatus.IN_PROGRESS)
        dev = await self._agent_step(mission_id, org_id, "developer", memory,
                                     "Implement the solution and request any tools needed to ship.")
        self._cost(mission_id, org_id, "developer", "Model + build cost for implementation", Decimal("0.82"))
        memory.record_handoff("developer", "security")

        deploy_requested = "production.deploy" in dev.tool_requests
        for tool in dev.tool_requests:
            if tool != "production.deploy":
                self._evaluate_and_record(mission_id, org_id, "developer", tool)
        # The deploy gate is deterministic: governance requires human approval and
        # the mission genuinely pauses/resumes (unchanged approval flow).
        deploy_ok = await self._deploy_with_approval(mission_id, org_id, budget)
        if not deploy_ok:
            self._set_agent(mission_id, org_id, "developer", AgentStatus.IDLE)
            self._transition(mission_id, MissionStatus.REJECTED)
            self._emit(mission_id, "mission.rejected", "system",
                       "Mission stopped safely: production deployment was rejected by a human reviewer.")
            return
        if not deploy_requested:
            self._emit(mission_id, "agent.message", "security",
                       "Note: deployment gate enforced by governance regardless of agent request.",
                       {"conversation": True})

        # Security — review + a governed scan; unauthorized export is blocked.
        await self._agent_step(mission_id, org_id, "security", memory,
                               "Review threats and data-access policy.")
        self._evaluate_and_record(mission_id, org_id, "security", "security.scan")
        await self._export_blocked(mission_id, org_id)
        memory.record_handoff("security", "qa")

        # QA — validate: run tests -> find issue -> developer fixes -> re-validate
        self._transition(mission_id, MissionStatus.VALIDATING)
        self._set_task_status(mission_id, "qa", TaskStatus.IN_PROGRESS)
        qa1 = await self._agent_step(mission_id, org_id, "qa", memory, "Run tests and report issues.")
        self._evaluate_and_record(mission_id, org_id, "qa", "qa.run_tests")
        issue = (qa1.output_dict.get("issues") or ["an authentication edge case"])[0]
        self._emit(mission_id, "qa.issue_found", "qa", f"QA Agent found an issue: {issue}.",
                   {"decision": qa1.output_dict})
        memory.record_handoff("qa", "developer")

        self._transition(mission_id, MissionStatus.RUNNING)
        devfix = await self._agent_step(mission_id, org_id, "developer", memory,
                                        "Fix the issue QA reported.", extra_context={"mode": "fix"})
        self._emit(mission_id, "issue.fixed", "developer", "Developer Agent fixed the reported issue.",
                   {"decision": devfix.output_dict})
        self._set_task_status(mission_id, "developer", TaskStatus.DONE)
        self._set_agent(mission_id, org_id, "developer", AgentStatus.COMPLETED)
        memory.record_handoff("developer", "qa")

        self._transition(mission_id, MissionStatus.VALIDATING)
        qa2 = await self._agent_step(mission_id, org_id, "qa", memory,
                                     "Re-validate the fix.", extra_context={"revalidate": True})
        self._emit(mission_id, "qa.passed", "qa", "QA Agent validated the final build.",
                   {"decision": qa2.output_dict})
        self._set_task_status(mission_id, "qa", TaskStatus.DONE)
        self._set_agent(mission_id, org_id, "qa", AgentStatus.COMPLETED)

        # Complete
        self._complete_remaining_agents(mission_id, org_id)
        self._transition(mission_id, MissionStatus.COMPLETED)
        await self._pace()
        self._emit(mission_id, "mission.completed", "system",
                   "Mission completed. All actions are auditable.")

        # Sprint 4: evaluate every agent, propose governed improvements, evolve.
        await self._pace()
        try:
            from app.evolution.service import evolution_service

            evolution_service.evaluate_mission(mission_id)
        except Exception as exc:  # noqa: BLE001 — evolution must never break a completed mission
            self._emit(mission_id, "evolution.failed", "system", f"Evolution step skipped: {exc}")

        # Real action: publish the mission report (grounded in the audit trail) to
        # cited.md so other agents can find, cite, and pay for it.
        await self._pace()
        try:
            from app.publishing.report import build_mission_report

            with session_scope() as session:
                title, markdown = build_mission_report(session, mission_id)
            url = await self.publisher.publish(title, markdown, {"mission_id": str(mission_id)})
            self._emit(mission_id, "mission.published", "finance",
                       "Mission report published to cited.md." if url
                       else "Mission report generated (set CITED_API_KEY to publish to cited.md).",
                       {"url": url, "chars": len(markdown), "provider": self.publisher.name})
        except Exception as exc:  # noqa: BLE001 — publishing must never break a completed mission
            self._emit(mission_id, "publish.failed", "system", f"Publish step skipped: {exc}")

    # --- workflow sub-steps -------------------------------------------------
    def _create_tasks_from(self, mission_id: uuid.UUID, org_id: uuid.UUID, titles: list[str]) -> None:
        """Persist the PM agent's decomposed tasks, assigned round-robin to teams."""
        titles = titles or ["Deliver the mission objective"]
        assignees = ["developer", "security", "qa", "finance"]
        with session_scope() as session:
            agents = AgentRepository(session)
            tasks = TaskRepository(session)
            for i, title in enumerate(titles):
                agent = agents.get_by_key(org_id, assignees[i % len(assignees)])
                tasks.create(mission_id, str(title)[:500], agent.id if agent else None)

    def _set_task_status(self, mission_id: uuid.UUID, agent_key: str, status: TaskStatus) -> None:
        with session_scope() as session:
            agent = AgentRepository(session).get_by_key(
                MissionRepository(session).get(mission_id).organization_id, agent_key
            )
            for task in TaskRepository(session).list_for_mission(mission_id):
                if agent and task.agent_id == agent.id:
                    TaskRepository(session).set_status(task, status)

    def _evaluate_and_record(self, mission_id: uuid.UUID, org_id: uuid.UUID, agent_key: str,
                             tool: str, resource: str | None = None,
                             estimated_cost_usd: float = 0.0) -> DecisionResult:
        with session_scope() as session:
            agent = AgentRepository(session).get_by_key(org_id, agent_key)
            mission = MissionRepository(session).get(mission_id)
            spent = float(CostRepository(session).total_for_mission(mission_id))
            req = ActionRequest(
                tool=tool, agent_role=agent.role if agent else agent_key,
                environment=DEPLOY_ENVIRONMENT, resource=resource,
                estimated_cost_usd=estimated_cost_usd,
                agent_budget_usd=float(agent.budget_limit_usd) if agent else None,
                mission_budget_usd=float(mission.budget_usd), mission_spent_usd=spent,
                agent_id=str(agent.id) if agent else None,
            )
            decision = self.governance.evaluate(req)
            GovernanceDecisionRepository(session).create(
                mission_id=mission_id, tool=tool, environment=DEPLOY_ENVIRONMENT,
                result=decision.result, risk_score=decision.risk_score, reason=decision.reason,
                policy_id=decision.policy_id, resource=resource, agent_id=agent.id if agent else None,
            )
        self._emit(mission_id, "governance.decision", "security",
                   f"{tool}: {decision.result.value}.",
                   {"tool": tool, "resource": resource, "result": decision.result.value,
                    "risk_score": decision.risk_score, "reason": decision.reason,
                    "policy_id": decision.policy_id})
        return decision

    async def _deploy_with_approval(self, mission_id: uuid.UUID, org_id: uuid.UUID, budget: Decimal) -> bool:
        self._set_agent(mission_id, org_id, "security", AgentStatus.WORKING)
        await self._pace()
        decision = self._evaluate_and_record(mission_id, org_id, "developer",
                                             "production.deploy", "support-portal-v1", 0.0)
        if decision.result is not DecisionResult.APPROVAL_REQUIRED:
            self._emit(mission_id, "deploy.succeeded", "developer",
                       "Developer Agent deployed support-portal-v1 to production.")
            return True

        # Create approval record + pause the mission
        with session_scope() as session:
            agent = AgentRepository(session).get_by_key(org_id, "developer")
            approval = ApprovalRepository(session).create(
                mission_id=mission_id, tool="production.deploy", resource="support-portal-v1",
                reason=decision.reason, policy_id=decision.policy_id, risk_score=decision.risk_score,
                agent_id=agent.id if agent else None,
            )
            approval_id = approval.id
        self._set_agent(mission_id, org_id, "developer", AgentStatus.WAITING_APPROVAL)
        self._transition(mission_id, MissionStatus.WAITING_APPROVAL)
        self._emit(mission_id, "approval.requested", "security",
                   "Human approval required before deploying to production.",
                   {"approval_id": str(approval_id), "tool": "production.deploy",
                    "resource": "support-portal-v1", "risk_score": decision.risk_score,
                    "policy_id": decision.policy_id})
        self._emit(mission_id, "mission.paused", "system",
                   "Mission paused, awaiting human approval for production deployment.")
        await self._mirror_event(mission_id, "governance", "approval_required",
                                 "Production deploy needs human approval (risk "
                                 f"{decision.risk_score}/100).")

        # >>> Genuinely pause until a real approve/reject API call arrives. <<<
        coordinator.register_wait(str(approval_id))
        outcome = await coordinator.wait_for_decision(str(approval_id))

        if outcome == "approved":
            self._transition(mission_id, MissionStatus.RUNNING)
            self._set_agent(mission_id, org_id, "developer", AgentStatus.WORKING)
            await self._pace()
            self._emit(mission_id, "deploy.succeeded", "developer",
                       "Developer Agent deployed support-portal-v1 to production.")
            return True
        return False

    async def _export_blocked(self, mission_id: uuid.UUID, org_id: uuid.UUID) -> None:
        self._set_agent(mission_id, org_id, "security", AgentStatus.WORKING)
        await self._pace()
        decision = self._evaluate_and_record(mission_id, org_id, "pm",
                                             "customer_database.export", "production_customers", 0.0)
        if decision.result is DecisionResult.BLOCK:
            self._emit(mission_id, "governance.blocked", "security",
                       "Blocked: an unauthorized agent attempted to export production customer data. "
                       "No data was exported.",
                       {"tool": "customer_database.export", "resource": "production_customers",
                        "policy_id": decision.policy_id})
            await self._mirror_event(mission_id, "governance", "blocked",
                                     "Blocked customer_database.export by an unauthorized agent.")
        self._set_agent(mission_id, org_id, "security", AgentStatus.COMPLETED)

    def _complete_remaining_agents(self, mission_id: uuid.UUID, org_id: uuid.UUID) -> None:
        with session_scope() as session:
            agents = AgentRepository(session)
            for agent in agents.list_for_org(org_id):
                if agent.status not in {AgentStatus.QUARANTINED, AgentStatus.COMPLETED}:
                    agents.set_status(agent, AgentStatus.COMPLETED)
