"""Resilient wrapper: timeout + retry + automatic fallback.

Wraps a primary provider and, on timeout or error after retries, transparently
serves from a fallback (the MockProvider) so a Gemini outage never crashes or
stalls the demo. The returned response reports whichever provider actually
served it, so cost/latency tracking stays accurate.
"""

from __future__ import annotations

import asyncio
import logging

from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger("swarmops.llm")


class ResilientProvider(LLMProvider):
    name = "resilient"

    def __init__(self, primary: LLMProvider, fallback: LLMProvider,
                 timeout_s: float = 20.0, max_retries: int = 2) -> None:
        self.primary = primary
        self.fallback = fallback
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.model = primary.model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                # wait_for raises TimeoutError on timeout; any error triggers fallback.
                return await asyncio.wait_for(self.primary.complete(request), timeout=self.timeout_s)
            except Exception as exc:  # noqa: BLE001 — resilience is the point
                last_error = exc
                logger.warning("LLM primary (%s) attempt %d/%d failed: %s",
                               self.primary.name, attempt, self.max_retries, exc)
        logger.warning("LLM falling back to %s after %d failed attempts: %s",
                       self.fallback.name, self.max_retries, last_error)
        return await self.fallback.complete(request)
