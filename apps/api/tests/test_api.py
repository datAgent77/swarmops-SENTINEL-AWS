"""HTTP integration tests over the ASGI app against the test database."""

import asyncio
import json
import uuid

import httpx

from app.main import app

BASE = "http://test"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


async def _poll(client: httpx.AsyncClient, mission_id: str, target: str, tries: int = 800) -> dict:
    for _ in range(tries):
        snap = (await client.get(f"/api/missions/{mission_id}")).json()
        if snap["mission"]["status"] == target:
            return snap
        await asyncio.sleep(0)
    raise AssertionError(f"mission {mission_id} never reached {target}")


async def test_health() -> None:
    async with _client() as c:
        assert (await c.get("/health")).json() == {"status": "ok"}


async def test_dashboard_exposes_org_and_six_agents() -> None:
    async with _client() as c:
        dash = (await c.get("/api/dashboard")).json()
    assert dash["organization"]["name"] == "SwarmOps Demo Org"
    assert {a["key"] for a in dash["agents"]} == {"ceo", "pm", "developer", "security", "qa", "finance"}


async def test_create_validation_error_envelope() -> None:
    async with _client() as c:
        resp = await c.post("/api/missions", json={"objective": "hi", "budget_usd": 5})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_unknown_mission_returns_not_found_envelope() -> None:
    async with _client() as c:
        resp = await c.get(f"/api/missions/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_full_happy_path_pause_approve_complete() -> None:
    async with _client() as c:
        created = (await c.post("/api/missions", json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()
        mid = created["id"]
        assert created["status"] == "created"

        paused = await _poll(c, mid, "waiting_approval")
        assert paused["pending_approval"]["tool"] == "production.deploy"
        approval_id = paused["pending_approval"]["id"]
        assert paused["metrics"]["approvals"] == 1

        resp = await c.post(f"/api/approvals/{approval_id}/approve")
        assert resp.status_code == 200

        done = await _poll(c, mid, "completed")
        assert done["pending_approval"] is None
        assert done["metrics"]["blocked"] == 1
        assert done["metrics"]["tasks_done"] >= 1
        assert float(done["metrics"]["total_cost_usd"]) > 0

        events = (await c.get(f"/api/missions/{mid}/events")).json()
        types = [e["type"] for e in events]
        seqs = [e["seq"] for e in events]
        assert seqs == sorted(seqs)  # stable ordering
        assert types[0] == "mission.started"
        assert "mission.completed" in types  # evolution events follow completion
        for expected in ("governance.decision", "approval.requested", "approval.granted",
                         "deploy.succeeded", "governance.blocked", "qa.issue_found",
                         "issue.fixed", "qa.passed"):
            assert expected in types, expected
        # deploy happens only after approval
        assert types.index("deploy.succeeded") > types.index("approval.granted")


async def test_reject_flow_stops_safely() -> None:
    async with _client() as c:
        created = (await c.post("/api/missions", json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()
        mid = created["id"]
        paused = await _poll(c, mid, "waiting_approval")
        approval_id = paused["pending_approval"]["id"]

        assert (await c.post(f"/api/approvals/{approval_id}/reject")).status_code == 200
        rejected = await _poll(c, mid, "rejected")
        assert rejected["pending_approval"] is None

        types = [e["type"] for e in (await c.get(f"/api/missions/{mid}/events")).json()]
        assert "approval.rejected" in types
        assert "mission.rejected" in types
        assert "deploy.succeeded" not in types


async def test_approve_unknown_id_404() -> None:
    async with _client() as c:
        resp = await c.post(f"/api/approvals/{uuid.uuid4()}/approve")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_double_resolution_returns_conflict() -> None:
    async with _client() as c:
        created = (await c.post("/api/missions", json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()
        mid = created["id"]
        approval_id = (await _poll(c, mid, "waiting_approval"))["pending_approval"]["id"]
        await c.post(f"/api/approvals/{approval_id}/approve")
        await _poll(c, mid, "completed")
        again = await c.post(f"/api/approvals/{approval_id}/approve")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "CONFLICT"


async def test_audit_persists_for_new_client_after_completion() -> None:
    """The backend is the source of truth: a brand-new client sees full history."""
    async with _client() as c:
        created = (await c.post("/api/missions", json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()
        mid = created["id"]
        approval_id = (await _poll(c, mid, "waiting_approval"))["pending_approval"]["id"]
        await c.post(f"/api/approvals/{approval_id}/approve")
        await _poll(c, mid, "completed")

    # Fresh client / connection — data comes from Postgres, not memory.
    async with _client() as c2:
        snap = (await c2.get(f"/api/missions/{mid}")).json()
        events = (await c2.get(f"/api/missions/{mid}/events")).json()
    assert snap["mission"]["status"] == "completed"
    assert len(events) > 10


async def test_sse_replays_ordered_events_and_closes() -> None:
    async with _client() as c:
        created = (await c.post("/api/missions", json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()
        mid = created["id"]
        approval_id = (await _poll(c, mid, "waiting_approval"))["pending_approval"]["id"]
        await c.post(f"/api/approvals/{approval_id}/approve")
        await _poll(c, mid, "completed")

        # Stream after completion: backlog replays in order and closes on terminal event.
        seqs, types = [], []
        async with c.stream("GET", f"/api/missions/{mid}/stream") as r:
            async for line in r.aiter_lines():
                if line.startswith("id: "):
                    seqs.append(int(line[4:]))
                elif line.startswith("data: "):
                    types.append(json.loads(line[6:])["type"])
    assert seqs == sorted(seqs)
    assert types[-1] == "mission.completed"


async def test_sse_last_event_id_resumes_after_seq() -> None:
    async with _client() as c:
        created = (await c.post("/api/missions", json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()
        mid = created["id"]
        approval_id = (await _poll(c, mid, "waiting_approval"))["pending_approval"]["id"]
        await c.post(f"/api/approvals/{approval_id}/approve")
        await _poll(c, mid, "completed")

        all_events = (await c.get(f"/api/missions/{mid}/events")).json()
        midpoint = all_events[len(all_events) // 2]["seq"]

        seen = []
        async with c.stream("GET", f"/api/missions/{mid}/stream",
                            headers={"Last-Event-ID": str(midpoint)}) as r:
            async for line in r.aiter_lines():
                if line.startswith("id: "):
                    seen.append(int(line[4:]))
    assert seen  # got something
    assert min(seen) > midpoint  # nothing at or before the checkpoint


async def test_ai_agents_drive_the_workflow_with_reasoning_and_tokens() -> None:
    """Sprint 2: real agent reasoning/conversation events + token tracking,
    while governance still pauses, blocks, and completes deterministically."""
    async with _client() as c:
        created = (await c.post("/api/missions", json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()
        mid = created["id"]
        approval_id = (await _poll(c, mid, "waiting_approval"))["pending_approval"]["id"]
        await c.post(f"/api/approvals/{approval_id}/approve")
        done = await _poll(c, mid, "completed")

        events = (await c.get(f"/api/missions/{mid}/events")).json()
        types = {e["type"] for e in events}
        # AI-driven signals
        assert {"agent.thinking", "agent.reasoning", "agent.message"} <= types
        # A real conversation between the six employees
        conversation = [e for e in events if e["type"] == "agent.message"]
        assert len(conversation) >= 5
        # Every reasoning event carries token/provider telemetry
        reasoning = [e for e in events if e["type"] == "agent.reasoning"]
        assert all("provider" in e["payload"] and "input_tokens" in e["payload"] for e in reasoning)
        # Token metrics are tracked and non-zero
        m = done["metrics"]
        assert m["llm_calls"] >= 6
        assert m["input_tokens"] > 0 and m["output_tokens"] > 0
        # Governance guarantees preserved
        assert m["blocked"] == 1
        assert "governance.blocked" in types and "deploy.succeeded" in types
