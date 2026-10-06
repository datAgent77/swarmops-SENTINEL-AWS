"""Sentinel API — AI Security Officer for Ring.

Thin HTTP surface over the Sentinel engines (Ring sensing, Bedrock perception,
deterministic governance, the officer service, and the Alexa+ MCP server). All
authority and state live in the services; this module only wires routers.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import governance, perception, ring, sentinel
from app.api.errors import register_error_handlers
from app.config import get_settings
from app.mcp import server as mcp_server

settings = get_settings()

app = FastAPI(title="Sentinel API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(ring.router)
app.include_router(perception.router)
app.include_router(governance.router)
app.include_router(sentinel.router)
app.include_router(mcp_server.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
