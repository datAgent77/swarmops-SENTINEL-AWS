"""Sprint 4 — self-evolving workforce: evaluation, weakness detection, versioning,
approval workflow, activation, and rollback."""

import asyncio

import httpx

from app.db.session import session_scope
from app.domain.enums import RiskLevel, VersionStatus
from app.evolution.improvement import ImprovementEngine
from app.evolution.policy import EvolutionPolicy
from app.evolution.versioning import VersionManager
from app.main import app
from app.repositories import AgentRepository, OrganizationRepository, VersionRepository

BASE = "http://test"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


async def _poll(c, mid, target, tries=3000):
    for _ in range(tries):
        s = (await c.get(f"/api/missions/{mid}")).json()
        if s["mission"]["status"] == target:
            return s
        await asyncio.sleep(0)
    raise AssertionError(f"never reached {target}")


async def _run_and_complete(c) -> str:
    mid = (await c.post("/api/missions", json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()["id"]
    ap = (await _poll(c, mid, "waiting_approval"))["pending_approval"]["id"]
    await c.post(f"/api/approvals/{ap}/approve")
    await _poll(c, mid, "completed")
    for _ in range(2000):  # let the evolution step settle
        await asyncio.sleep(0)
    return mid


def _by_key(cards):
    return {c["agent_key"]: c for c in cards}


# --- unit: policy -------------------------------------------------------------
def test_policy_classifies_risk() -> None:
    p = EvolutionPolicy()
    assert p.classify("security") is RiskLevel.HIGH
    assert p.classify("budget") is RiskLevel.HIGH
    assert p.classify("planning") is RiskLevel.LOW
    assert p.classify_many(["planning", "security"]) is RiskLevel.HIGH
    assert p.classify_many(["planning", "reasoning"]) is RiskLevel.LOW


# --- unit: improvement engine -------------------------------------------------
def test_improvement_engine_maps_weaknesses() -> None:
    eng = ImprovementEngine()
    s = eng.suggest([{"code": "high_security_violations"}, {"code": "high_deployment_approval_rate"}])
    risks = {x["weakness"]: x["risk"] for x in s}
    assert risks["high_security_violations"] == "high"
    assert risks["high_deployment_approval_rate"] == "low"
    delta = eng.projected_delta(80.0, s)
    assert delta["score_after"] > 80.0


# --- integration: evaluation produces reports + versions ----------------------
async def test_evaluation_creates_reports_and_versions() -> None:
    async with _client() as c:
        await _run_and_complete(c)
        cards = (await c.get("/api/evolution/agents")).json()
        assert len(cards) == 6
        assert all(x["performance_score"] > 0 for x in cards)
        by = _by_key(cards)
        # Developer's low-risk improvement auto-activated to v1.1.
        assert by["developer"]["current_version"] == "1.1"
        # PM's high-risk improvement is pending governance approval.
        assert by["pm"]["pending_version"] is not None
        assert by["pm"]["pending_version"]["risk_level"] == "high"
        assert by["pm"]["current_version"] == "1.0"


# --- integration: high-risk approval workflow + activation --------------------
async def test_high_risk_version_requires_approval_then_activates() -> None:
    async with _client() as c:
        await _run_and_complete(c)
        vid = _by_key((await c.get("/api/evolution/agents")).json())["pm"]["pending_version"]["id"]
        resp = await c.post(f"/api/evolution/versions/{vid}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        by = _by_key((await c.get("/api/evolution/agents")).json())
        assert by["pm"]["current_version"] == "1.1"
        assert by["pm"]["pending_version"] is None
        # resolving again is a safe conflict
        assert (await c.post(f"/api/evolution/versions/{vid}/approve")).status_code == 409


async def test_high_risk_version_can_be_rejected() -> None:
    async with _client() as c:
        await _run_and_complete(c)
        vid = _by_key((await c.get("/api/evolution/agents")).json())["pm"]["pending_version"]["id"]
        resp = await c.post(f"/api/evolution/versions/{vid}/reject")
        assert resp.json()["status"] == "rejected"
        by = _by_key((await c.get("/api/evolution/agents")).json())
        assert by["pm"]["current_version"] == "1.0"  # unchanged


# --- unit: version manager create/activate/rollback ---------------------------
def test_version_manager_activate_and_rollback() -> None:
    with session_scope() as s:
        org = OrganizationRepository(s).get_default()
        agent = AgentRepository(s).get_by_key(org.id, "developer")
        vm = VersionManager()
        baseline = vm.ensure_baseline(s, agent)
        assert baseline.version == "1.0"
        v11 = vm.propose(s, agent, [{"weakness": "x"}], {"a": 1}, {}, RiskLevel.LOW, "reason")
        vm.activate(s, v11)
        repo = VersionRepository(s)
        assert repo.active_for_agent("developer").version == "1.1"
        # rollback to the baseline — history preserved, v1.0 active again
        vm.rollback(s, "developer", baseline.id)
        assert repo.active_for_agent("developer").version == "1.0"
        versions = repo.list_for_agent("developer")
        assert {v.version for v in versions} == {"1.0", "1.1"}  # nothing overwritten
        assert any(v.status == VersionStatus.SUPERSEDED for v in versions)


# --- integration: mission summary ---------------------------------------------
async def test_mission_summary_ranks_agents() -> None:
    async with _client() as c:
        mid = await _run_and_complete(c)
        sm = (await c.get(f"/api/missions/{mid}/summary")).json()
        assert sm["top_performer"]
        assert sm["highest_risk_agent"]
        assert sm["most_improved"]
        assert len(sm["reports"]) == 6
