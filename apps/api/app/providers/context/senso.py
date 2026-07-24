"""Senso (senso.ai) context layer — ingest mission artifacts and retrieve
agent-ready context via Senso's REST API (auth header ``X-API-Key``).

Best-effort: on any error the provider degrades to a silent no-op for the rest of
the run. The endpoint paths and body field names follow Senso's "ingest / query /
generate" API and are kept here so they are trivial to align with the live API
reference (docs.senso.ai).
"""

from __future__ import annotations

import logging

import httpx

from app.providers.context.base import ContextProvider

log = logging.getLogger("swarmops.context.senso")


class SensoContext(ContextProvider):
    name = "senso"

    def __init__(self, api_key: str, base_url: str = "https://api.senso.ai/v1",
                 timeout_s: float = 5.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._degraded = False

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "content-type": "application/json"}

    async def ingest(self, text: str, source: str, meta: dict | None = None) -> None:
        if self._degraded or not text:
            return
        body = {"text": text, "source": source, "metadata": meta or {}}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.base_url}/content", headers=self._headers(), json=body)
            if resp.status_code >= 300:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:160]}")
        except Exception as exc:  # noqa: BLE001 — context must never break a mission
            self._degrade(exc)

    async def query(self, question: str, k: int = 4) -> str:
        if self._degraded or not question:
            return ""
        body = {"query": question, "max_results": k}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.base_url}/search", headers=self._headers(), json=body)
            if resp.status_code >= 300:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:160]}")
            data = resp.json()
            return self._extract(data)
        except Exception as exc:  # noqa: BLE001 — best-effort retrieval
            self._degrade(exc)
            return ""

    @staticmethod
    def _extract(data: object) -> str:
        # Tolerate a few likely response shapes: {"answer": ...},
        # {"content": ...}, or {"results": [{"text": ...}, ...]}.
        if isinstance(data, dict):
            if isinstance(data.get("answer"), str):
                return data["answer"]
            if isinstance(data.get("content"), str):
                return data["content"]
            results = data.get("results")
            if isinstance(results, list):
                parts = [r.get("text") or r.get("content") for r in results if isinstance(r, dict)]
                return " ".join(p for p in parts if p)[:800]
        return ""

    def _degrade(self, exc: Exception) -> None:
        if not self._degraded:
            log.warning("Senso context disabled for this run after error: %s", exc)
        self._degraded = True
