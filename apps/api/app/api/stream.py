"""Server-Sent Events for a mission.

Events are durable in PostgreSQL; this endpoint reads committed events (ordered
by the global ``seq``), then waits on an in-process wake-up signal and re-reads
new events from the database. It supports Last-Event-ID reconnection, emits
periodic keep-alives, and disconnects cleanly.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.db.session import SessionLocal
from app.domain.errors import NotFoundError
from app.domain.schemas import EventRead
from app.orchestration.coordinator import coordinator
from app.repositories import EventRepository, MissionRepository

router = APIRouter(prefix="/api", tags=["stream"])

TERMINAL_EVENTS = {"mission.completed", "mission.rejected", "mission.failed"}
KEEPALIVE_SECONDS = 15


def _mission_exists(mission_id: uuid.UUID) -> bool:
    with SessionLocal() as session:
        return MissionRepository(session).get(mission_id) is not None


def _events_after(mission_id: uuid.UUID, after_seq: int) -> list[EventRead]:
    with SessionLocal() as session:
        rows = EventRepository(session).list_for_mission(mission_id, after_seq=after_seq or None)
        return [EventRead.model_validate(r) for r in rows]


def _format(event: EventRead) -> str:
    data = json.dumps(event.model_dump(mode="json"))
    # No SSE `event:` line: keep everything on the default "message" channel so the
    # browser EventSource `onmessage` handler receives them. The type is in `data`.
    return f"id: {event.seq}\ndata: {data}\n\n"


@router.get("/missions/{mission_id}/stream")
async def stream(mission_id: uuid.UUID, request: Request) -> StreamingResponse:
    if not await run_in_threadpool(_mission_exists, mission_id):
        raise NotFoundError("Mission not found", {"mission_id": str(mission_id)})

    last_header = request.headers.get("last-event-id")
    start_seq = int(last_header) if last_header and last_header.isdigit() else 0
    queue = coordinator.subscribe(str(mission_id))

    async def generator():
        last = start_seq
        try:
            # Replay backlog (supports reconnection via Last-Event-ID).
            for event in await run_in_threadpool(_events_after, mission_id, last):
                last = event.seq
                yield _format(event)
                if event.type in TERMINAL_EVENTS:
                    return
            # Live tail.
            while True:
                if await request.is_disconnected():
                    return
                try:
                    await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                for event in await run_in_threadpool(_events_after, mission_id, last):
                    last = event.seq
                    yield _format(event)
                    if event.type in TERMINAL_EVENTS:
                        return
        finally:
            coordinator.unsubscribe(str(mission_id), queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
