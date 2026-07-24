"""Gemini provider (Google Generative Language REST API via httpx).

Uses JSON response mode so agents return structured output. Kept dependency-light
(httpx only) and lazy: if no key or the call fails, the resilient wrapper falls
back to the MockProvider. Business logic never imports this class directly.
"""

from __future__ import annotations

import time

import httpx

from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse, LLMUsage, estimate_tokens

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProviderError(RuntimeError):
    pass


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", timeout_s: float = 20.0) -> None:
        if not api_key:
            raise GeminiProviderError("GEMINI_API_KEY is required for GeminiProvider")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    async def complete(self, request: LLMRequest) -> LLMResponse:
        body = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
                "responseMimeType": "application/json",
            },
        }
        url = _ENDPOINT.format(model=self.model)
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, params={"key": self.api_key}, json=body)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code != 200:
            raise GeminiProviderError(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise GeminiProviderError(f"Unexpected Gemini response shape: {exc}") from exc
        meta = data.get("usageMetadata", {})
        usage = LLMUsage(
            input_tokens=int(meta.get("promptTokenCount", estimate_tokens(request.user_prompt))),
            output_tokens=int(meta.get("candidatesTokenCount", estimate_tokens(text))),
        )
        return LLMResponse(text=text, usage=usage, provider=self.name, model=self.model,
                           latency_ms=latency_ms, raw=data)
