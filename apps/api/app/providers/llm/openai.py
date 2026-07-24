"""OpenAI provider (Chat Completions API via httpx).

Uses JSON response mode (`response_format: json_object`) so agents return
structured output. Dependency-light (httpx only) and lazy; on failure the
resilient wrapper falls back to the MockProvider. Business logic never imports
this class directly.
"""

from __future__ import annotations

import time

import httpx

from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse, LLMUsage, estimate_tokens

_ENDPOINT = "https://api.openai.com/v1/chat/completions"


class OpenAIProviderError(RuntimeError):
    pass


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout_s: float = 20.0) -> None:
        if not api_key:
            raise OpenAIProviderError("OPENAI_API_KEY is required for OpenAIProvider")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    async def complete(self, request: LLMRequest) -> LLMResponse:
        body = {
            "model": self.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(_ENDPOINT, headers=headers, json=body)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code != 200:
            raise OpenAIProviderError(f"OpenAI HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise OpenAIProviderError(f"Unexpected OpenAI response shape: {exc}") from exc
        meta = data.get("usage", {})
        usage = LLMUsage(
            input_tokens=int(meta.get("prompt_tokens", estimate_tokens(request.user_prompt))),
            output_tokens=int(meta.get("completion_tokens", estimate_tokens(text))),
        )
        return LLMResponse(text=text, usage=usage, provider=self.name, model=self.model,
                           latency_ms=latency_ms, raw=data)
