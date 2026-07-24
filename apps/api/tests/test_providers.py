"""LLM provider abstraction: structured output, pricing, and resilient fallback."""

import asyncio
import json

import pytest

from app.providers.llm import LLMRequest, MockProvider, ResilientProvider, get_provider
from app.providers.llm.base import LLMProvider, LLMResponse, LLMUsage
from app.providers.llm.pricing import estimate_cost

ROLE_KEYS = {
    "ceo": {"plan", "reasoning", "risks", "confidence", "nextAgent"},
    "pm": {"tasks", "dependencies", "estimatedDuration", "confidence", "nextAgent"},
    "developer": {"implementation", "risks", "toolRequests", "nextAgent"},
    "qa": {"issues", "severity", "passed", "nextAgent"},
    "security": {"securityReview", "violations", "recommendedActions"},
    "finance": {"estimatedCost", "budgetStatus", "recommendation"},
}


@pytest.mark.parametrize("role,keys", list(ROLE_KEYS.items()))
async def test_mock_returns_valid_structured_output(role: str, keys: set[str]) -> None:
    provider = MockProvider()
    resp = await provider.complete(
        LLMRequest(system_prompt="s", user_prompt="u", schema_name=role, context={"objective": "x"})
    )
    assert set(json.loads(resp.text)) >= keys
    assert resp.provider == "mock"
    assert resp.usage.total_tokens > 0


class _Boom(LLMProvider):
    name = "boom"
    model = "boom"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("simulated outage")


class _Slow(LLMProvider):
    name = "slow"
    model = "slow"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        await asyncio.sleep(5)
        raise AssertionError("should have timed out")


async def test_resilient_falls_back_on_error() -> None:
    res = ResilientProvider(_Boom(), MockProvider(), timeout_s=0.5, max_retries=2)
    resp = await res.complete(LLMRequest(system_prompt="s", user_prompt="u", schema_name="ceo"))
    assert resp.provider == "mock"


async def test_resilient_falls_back_on_timeout() -> None:
    res = ResilientProvider(_Slow(), MockProvider(), timeout_s=0.05, max_retries=1)
    resp = await res.complete(LLMRequest(system_prompt="s", user_prompt="u", schema_name="ceo"))
    assert resp.provider == "mock"


def test_pricing_scales_with_tokens() -> None:
    small = estimate_cost("mock-1", LLMUsage(1000, 1000))
    large = estimate_cost("mock-1", LLMUsage(2000, 2000))
    assert large > small > 0


def test_get_provider_defaults_to_mock_without_key() -> None:
    provider = get_provider()
    assert isinstance(provider, ResilientProvider)
    assert provider.primary.name == "mock"  # no LLM key configured in tests


# --- provider selection (Claude / OpenAI / Gemini / Mock) ---------------------
@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Prevent env changes in these tests from leaking via the settings cache."""
    yield
    from app.config import get_settings as _gs
    _gs.cache_clear()


def _provider_with_env(monkeypatch, **env):
    from app.config import get_settings as _gs
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    _gs.cache_clear()
    return get_provider()


def test_factory_selects_claude(monkeypatch) -> None:
    p = _provider_with_env(monkeypatch, LLM_PROVIDER="claude", ANTHROPIC_API_KEY="sk-ant-test")
    assert p.primary.name == "claude"


def test_factory_selects_openai(monkeypatch) -> None:
    p = _provider_with_env(monkeypatch, LLM_PROVIDER="openai", OPENAI_API_KEY="sk-test")
    assert p.primary.name == "openai"


def test_factory_auto_prefers_claude_then_openai(monkeypatch) -> None:
    p = _provider_with_env(monkeypatch, LLM_PROVIDER="auto",
                           ANTHROPIC_API_KEY="sk-ant-test", OPENAI_API_KEY="sk-test")
    assert p.primary.name == "claude"


def test_factory_auto_uses_openai_when_only_openai_key(monkeypatch) -> None:
    p = _provider_with_env(monkeypatch, LLM_PROVIDER="auto", OPENAI_API_KEY="sk-test")
    assert p.primary.name == "openai"


def test_factory_forced_mock_ignores_keys(monkeypatch) -> None:
    p = _provider_with_env(monkeypatch, LLM_PROVIDER="mock", ANTHROPIC_API_KEY="sk-ant-test")
    assert p.primary.name == "mock"
