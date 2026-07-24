"""No-op comms used by default and in tests. The Postgres audit trail remains the
source of truth for the conversation; this simply does nothing when no external
comms provider (Band) is configured."""

from __future__ import annotations

from app.providers.comms.base import CommsProvider


class LocalComms(CommsProvider):
    name = "local"

    async def ensure_room(self, mission_id: str, title: str) -> str:
        return f"local:{mission_id}"

    async def send_message(self, room_id: str, sender: str, content: str,
                           mentions: list[str] | None = None) -> None:
        return None

    async def post_event(self, room_id: str, sender: str, kind: str, content: str) -> None:
        return None
