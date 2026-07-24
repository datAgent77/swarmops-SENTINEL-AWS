"""No-op context provider used by default and in tests. Mission memory remains the
working context; nothing external is called when no Senso key is configured."""

from __future__ import annotations

from app.providers.context.base import ContextProvider


class LocalContext(ContextProvider):
    name = "local"

    async def ingest(self, text: str, source: str, meta: dict | None = None) -> None:
        return None

    async def query(self, question: str, k: int = 4) -> str:
        return ""
