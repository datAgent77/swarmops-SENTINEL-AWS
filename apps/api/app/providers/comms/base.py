"""The comms provider interface. Mirrors the LLM provider pattern: one small
abstract surface that business logic depends on, with swappable implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CommsProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def ensure_room(self, mission_id: str, title: str) -> str:
        """Return a room/channel id for this mission (creating one if needed)."""

    @abstractmethod
    async def send_message(self, room_id: str, sender: str, content: str,
                           mentions: list[str] | None = None) -> None:
        """Publish an inter-agent message to the room."""

    @abstractmethod
    async def post_event(self, room_id: str, sender: str, kind: str, content: str) -> None:
        """Publish a non-message event (a thought, a governance decision, …)."""

    async def aclose(self) -> None:  # pragma: no cover - optional cleanup
        return None
