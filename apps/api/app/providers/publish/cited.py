"""cited.md publisher — pushes the mission report to cited.md (Senso's endpoint
for the agentic web) so other agents can find, cite, and pay for it.

Best-effort: on any error it degrades to no external URL (the report is still
served locally). The exact request path and body fields follow cited.md's publish
API and are centralized here so they are trivial to align with the live reference.
"""

from __future__ import annotations

import logging

import httpx

from app.providers.publish.base import PublishProvider

log = logging.getLogger("swarmops.publish.cited")


class CitedPublisher(PublishProvider):
    name = "cited"

    def __init__(self, api_key: str, base_url: str = "https://cited.md/api",
                 timeout_s: float = 6.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    async def publish(self, title: str, markdown: str, meta: dict | None = None) -> str | None:
        body = {"title": title, "content": markdown, "format": "markdown", "metadata": meta or {}}
        headers = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.base_url}/publish", headers=headers, json=body)
            if resp.status_code >= 300:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:160]}")
            data = resp.json()
            return str(data.get("url") or data.get("link") or data.get("permalink") or "") or None
        except Exception as exc:  # noqa: BLE001 — publishing must never break a mission
            log.warning("cited.md publish failed: %s", exc)
            return None
