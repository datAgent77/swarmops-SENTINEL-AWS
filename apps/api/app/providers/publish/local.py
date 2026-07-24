"""No-op publisher used when no cited.md key is configured. The report is still
generated and served via GET /api/missions/{id}/report; it just isn't pushed to
an external endpoint."""

from __future__ import annotations

from app.providers.publish.base import PublishProvider


class LocalPublisher(PublishProvider):
    name = "local"

    async def publish(self, title: str, markdown: str, meta: dict | None = None) -> str | None:
        return None
