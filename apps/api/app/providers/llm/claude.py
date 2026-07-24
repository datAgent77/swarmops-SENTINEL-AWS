"""Anthropic Claude provider (Messages API via httpx).

Uses assistant prefill (`{`) to force a JSON-object response so agents return
structured output. Dependency-light (httpx only) and lazy; on failure the
resilient wrapper falls back to the MockProvider. Business logic never imports
this class directly.
"""

from __future__ import annotations

import time

import httpx

from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse, LLMUsage, estimate_tokens

_ENDPOINT = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"


class ClaudeProviderError(RuntimeError):
    pass


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-latest", timeout_s: float = 20.0) -> None:
        if not api_key:
            raise ClaudeProviderError("ANTHROPIC_API_KEY is required for ClaudeProvider")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    async def complete(self, request: LLMRequest) -> LLMResponse:
        body = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": request.system_prompt,
            "messages": [
                {"role": "user", "content": request.user_prompt},
                {"role": "assistant", "content": "{"},  # prefill → forces a JSON object
            ],
        }
        headers = {"x-api-key": self.api_key, "anthropic-version": _VERSION, "content-type": "application/json"}
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(_ENDPOINT, headers=headers, json=body)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code != 200:
            raise ClaudeProviderError(f"Claude HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        try:
            # Re-add the prefilled '{' that the model continued from.
            text = "{" + data["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ClaudeProviderError(f"Unexpected Claude response shape: {exc}") from exc
        meta = data.get("usage", {})
        usage = LLMUsage(
            input_tokens=int(meta.get("input_tokens", estimate_tokens(request.user_prompt))),
            output_tokens=int(meta.get("output_tokens", estimate_tokens(text))),
        )
        return LLMResponse(text=text, usage=usage, provider=self.name, model=self.model,
                           latency_ms=latency_ms, raw=data)
