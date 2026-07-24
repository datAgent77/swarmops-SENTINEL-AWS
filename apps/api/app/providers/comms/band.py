"""Band (band.ai) comms — mirrors the agent conversation to a Band room via the
REST Agent API (base ``/api/v1``, auth header ``X-API-Key``).

Every call is best-effort: on any error the provider degrades to a silent no-op
for the rest of the run so a comms hiccup can never stall or fail a mission. The
exact request-body field names follow Band's Agent API (docs.band.ai); they are
kept in one place here so they are trivial to align with the live API reference.
"""

from __future__ import annotations

import logging

import httpx

from app.providers.comms.base import CommsProvider

log = logging.getLogger("swarmops.comms.band")


class BandComms(CommsProvider):
    name = "band"

    def __init__(self, api_key: str, base_url: str = "https://app.band.ai/api/v1",
                 agent_id: str | None = None, chat_id: str | None = None,
                 timeout_s: float = 5.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.configured_chat_id = chat_id
        self.timeout_s = timeout_s
        self._degraded = False

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "content-type": "application/json"}

    async def ensure_room(self, mission_id: str, title: str) -> str:
        # A pre-created room can be supplied via BAND_CHAT_ID; otherwise create one.
        if self.configured_chat_id:
            return self.configured_chat_id
        if self._degraded:
            return f"local:{mission_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.base_url}/agent/chats",
                                         headers=self._headers(),
                                         json={"title": title})
            if resp.status_code >= 300:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:160]}")
            data = resp.json()
            return str(data.get("id") or data.get("chat_id") or data.get("room_id") or f"local:{mission_id}")
        except Exception as exc:  # noqa: BLE001 — comms must never break a mission
            self._degrade(exc)
            return f"local:{mission_id}"

    async def send_message(self, room_id: str, sender: str, content: str,
                           mentions: list[str] | None = None) -> None:
        if self._degraded or room_id.startswith("local:"):
            return
        body = {"content": f"[{sender}] {content}", "mentions": mentions or []}
        await self._post(f"/agent/chats/{room_id}/messages", body)

    async def post_event(self, room_id: str, sender: str, kind: str, content: str) -> None:
        if self._degraded or room_id.startswith("local:"):
            return
        body = {"type": kind, "actor": sender, "content": content}
        await self._post(f"/agent/chats/{room_id}/events", body)

    async def _post(self, path: str, body: dict) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.base_url}{path}", headers=self._headers(), json=body)
            if resp.status_code >= 300:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:160]}")
        except Exception as exc:  # noqa: BLE001 — best-effort mirror
            self._degrade(exc)

    def _degrade(self, exc: Exception) -> None:
        if not self._degraded:
            log.warning("Band comms disabled for this run after error: %s", exc)
        self._degraded = True
