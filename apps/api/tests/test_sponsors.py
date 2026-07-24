"""Sponsor integrations — provider parity, key-gated selection, and the core
guarantee: a comms/context outage can never break a mission (best-effort mirror,
local no-op fallback), and Pioneer speaks the OpenAI-compatible shape.
"""

import asyncio

import httpx

from app.agents.agent import AgentRunner  # noqa: F401  (import sanity)
from app.providers.comms.band import BandComms
from app.providers.comms.factory import get_comms
from app.providers.comms.local import LocalComms
from app.providers.context.factory import get_context
from app.providers.context.local import LocalContext
from app.providers.context.senso import SensoContext
from app.providers.llm.base import LLMRequest
from app.providers.llm.pioneer import PioneerProvider

BASE = "http://test"
DEAD = "http://127.0.0.1:9"  # nothing listens here → connection refused


def _client() -> httpx.AsyncClient:
    from app.main import app

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


async def _poll(c, mid, target, tries=3000):
    for _ in range(tries):
        s = (await c.get(f"/api/missions/{mid}")).json()
        if s["mission"]["status"] == target:
            return s
        await asyncio.sleep(0)
    raise AssertionError(f"never reached {target}")


# --- selection: default to local no-op --------------------------------------
def test_comms_and_context_default_to_local() -> None:
    assert isinstance(get_comms(), LocalComms)
    assert isinstance(get_context(), LocalContext)


# --- the UI "tools in use" indicator reflects real config, no secrets --------
def test_active_sponsors_reflects_config(monkeypatch) -> None:
    from app.config import Settings

    assert Settings(_env_file=None).active_sponsors() == []
    monkeypatch.setenv("BAND_API_KEY", "b")
    monkeypatch.setenv("SENSO_API_KEY", "s")
    monkeypatch.setenv("PIONEER_KEY", "p")
    assert set(Settings(_env_file=None).active_sponsors()) == {"band", "senso", "pioneer"}


async def test_dashboard_exposes_sponsors_field() -> None:
    async with _client() as c:
        dash = (await c.get("/api/dashboard")).json()
    assert "sponsors" in dash and isinstance(dash["sponsors"], list)  # [] with no keys


# --- real action: the mission report is grounded and published --------------
async def test_mission_report_is_grounded_and_published() -> None:
    async with _client() as c:
        mid = (await c.post("/api/missions",
                            json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()["id"]
        ap = (await _poll(c, mid, "waiting_approval"))["pending_approval"]["id"]
        await c.post(f"/api/approvals/{ap}/approve")
        await _poll(c, mid, "completed")
        for _ in range(2000):  # let the evolution + publish steps settle
            await asyncio.sleep(0)

        rep = (await c.get(f"/api/missions/{mid}/report")).json()
        md = rep["markdown"]
        assert "Governance decisions" in md
        assert "deployment.production.human_approval" in md   # cites the real policy
        assert "Self-evolution" in md
        assert rep["url"] is None  # LocalPublisher when no CITED_API_KEY

        types = [e["type"] for e in (await c.get(f"/api/missions/{mid}/events")).json()]
        assert "mission.published" in types  # the report was published (real action)


# --- comms/context degrade gracefully when the vendor is unreachable ---------
async def test_band_comms_degrades_without_raising() -> None:
    band = BandComms(api_key="x", base_url=f"{DEAD}/api/v1")
    room = await band.ensure_room("mission-1", "title")
    assert room.startswith("local:")           # creation failed → local id
    await band.send_message(room, "ceo", "hello")   # no raise
    await band.post_event(room, "ceo", "note", "hi")  # no raise
    assert band._degraded is True


async def test_senso_context_degrades_without_raising() -> None:
    senso = SensoContext(api_key="x", base_url=f"{DEAD}/v1")
    assert await senso.query("what is the objective?") == ""  # failed → empty
    await senso.ingest("some text", source="ceo")             # no raise
    assert senso._degraded is True


def test_senso_extract_tolerates_shapes() -> None:
    assert SensoContext._extract({"answer": "A"}) == "A"
    assert SensoContext._extract({"content": "B"}) == "B"
    assert SensoContext._extract({"results": [{"text": "x"}, {"content": "y"}]}) == "x y"
    assert SensoContext._extract({"nope": 1}) == ""


# --- Pioneer speaks OpenAI-compatible chat completions with adaptive routing --
async def test_pioneer_provider_shape_and_adaptive(monkeypatch) -> None:
    captured = {}

    async def fake_post(self, url, headers=None, json=None):  # noqa: ANN001
        captured["url"] = url
        captured["body"] = json
        captured["auth"] = headers.get("Authorization")
        payload = {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            "model": "routed-slm-1",
        }
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    provider = PioneerProvider(api_key="pk", model="gemma")
    req = LLMRequest(system_prompt="sys", user_prompt="hi", temperature=0.2,
                     max_tokens=256, schema_name="ceo", context={})
    resp = await provider.complete(req)

    assert captured["url"].endswith("/chat/completions")
    assert captured["auth"] == "Bearer pk"
    assert captured["body"]["adaptive"] is True          # Pioneer adaptive routing
    assert resp.provider == "pioneer"
    assert resp.model == "routed-slm-1"                   # reports the routed model
    assert resp.usage.input_tokens == 11 and resp.usage.output_tokens == 7


# --- the guarantee: unreachable sponsors never break a mission ---------------
async def test_mission_completes_when_sponsors_are_unreachable() -> None:
    from app.services import mission_service as ms

    orch = ms._orchestrator
    saved_comms, saved_context = orch.comms, orch.context
    orch.comms = BandComms(api_key="x", base_url=f"{DEAD}/api/v1")
    orch.context = SensoContext(api_key="x", base_url=f"{DEAD}/v1")
    try:
        async with _client() as c:
            mid = (await c.post("/api/missions",
                                json={"objective": "Launch a secure portal.", "budget_usd": 5})).json()["id"]
            ap = (await _poll(c, mid, "waiting_approval"))["pending_approval"]["id"]
            await c.post(f"/api/approvals/{ap}/approve")
            done = await _poll(c, mid, "completed")
        assert done["mission"]["status"] == "completed"
    finally:
        orch.comms, orch.context = saved_comms, saved_context
