"""SwarmOps API — thin HTTP surface. All logic lives in services and repositories."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import approvals, evolution, governance, missions, perception, ring, stream
from app.api.errors import register_error_handlers
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="SwarmOps API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(missions.router)
app.include_router(approvals.router)
app.include_router(stream.router)
app.include_router(evolution.router)
app.include_router(ring.router)
app.include_router(perception.router)
app.include_router(governance.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
