"""Pioneer (Fastino) provider — OpenAI-compatible model routing / adaptive
inference. Same Chat Completions shape as OpenAI, with an ``adaptive`` flag that
lets Pioneer route/adapt the model. Dependency-light (httpx) and lazy; the
resilient wrapper falls back to Mock. Business logic never imports this directly.
"""

from __future__ import annotations

import time

import httpx

from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse, LLMUsage, estimate_tokens


class PioneerProviderError(RuntimeError):
    pass


class PioneerProvider(LLMProvider):
    name = "pioneer"

    def __init__(self, api_key: str, model: str = "gemma",
                 base_url: str = "https://api.pioneer.ai/v1",
                 adaptive: bool = True, timeout_s: float = 20.0) -> None:
        if not api_key:
            raise PioneerProviderError("PIONEER_KEY is required for PioneerProvider")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.adaptive = adaptive
        self.timeout_s = timeout_s

    async def complete(self, request: LLMRequest) -> LLMResponse:
        body = {
            "model": self.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "adaptive": self.adaptive,  # Pioneer-specific: enable adaptive routing
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code != 200:
            raise PioneerProviderError(f"Pioneer HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise PioneerProviderError(f"Unexpected Pioneer response shape: {exc}") from exc
        meta = data.get("usage", {})
        # Pioneer may report the model it actually routed to.
        routed_model = str(data.get("model") or self.model)
        usage = LLMUsage(
            input_tokens=int(meta.get("prompt_tokens", estimate_tokens(request.user_prompt))),
            output_tokens=int(meta.get("completion_tokens", estimate_tokens(text))),
        )
        return LLMResponse(text=text, usage=usage, provider=self.name, model=routed_model,
                           latency_ms=latency_ms, raw=data)
