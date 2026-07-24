"""In-process coordination for live streaming and approval resume.

This is intentionally lightweight and memory-resident: it only carries *wake-up
signals*, never the source of truth. Event durability lives in PostgreSQL — SSE
subscribers re-read committed events from the database when woken here, so a
dropped in-memory signal can never lose an event.
"""

from __future__ import annotations

import asyncio


class MissionCoordinator:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[int]]] = {}
        self._resume_events: dict[str, asyncio.Event] = {}
        self._outcomes: dict[str, str] = {}

    # --- SSE fan-out (bounded queues; DB is the durable backstop) ----------
    def subscribe(self, mission_id: str) -> asyncio.Queue[int]:
        queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1000)
        self._subscribers.setdefault(mission_id, set()).add(queue)
        return queue

    def unsubscribe(self, mission_id: str, queue: asyncio.Queue[int]) -> None:
        subs = self._subscribers.get(mission_id)
        if subs:
            subs.discard(queue)
            if not subs:
                self._subscribers.pop(mission_id, None)

    def publish(self, mission_id: str, seq: int) -> None:
        for queue in list(self._subscribers.get(mission_id, ())):
            try:
                queue.put_nowait(seq)
            except asyncio.QueueFull:
                # Subscriber is behind; it will catch up via a DB read on its
                # next wake. No event is lost because Postgres holds them all.
                pass

    # --- approval resume signaling ----------------------------------------
    def register_wait(self, approval_id: str) -> asyncio.Event:
        event = asyncio.Event()
        self._resume_events[approval_id] = event
        return event

    async def wait_for_decision(self, approval_id: str) -> str:
        # If a decision already arrived (race: approve before we started waiting),
        # return it immediately rather than blocking forever.
        if approval_id in self._outcomes:
            return self._outcomes[approval_id]
        event = self._resume_events.get(approval_id)
        if event is None:
            event = self.register_wait(approval_id)
        await event.wait()
        return self._outcomes.get(approval_id, "rejected")

    def signal_decision(self, approval_id: str, outcome: str) -> None:
        self._outcomes[approval_id] = outcome
        event = self._resume_events.get(approval_id)
        if event is not None:
            event.set()


# Process-wide singleton.
coordinator = MissionCoordinator()
