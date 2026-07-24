"""Provider selection. The only place that decides which concrete provider runs.

Selection: an explicit ``LLM_PROVIDER`` (claude|openai|gemini|pioneer|mock) wins;
"auto" picks the first provider whose API key is configured, in the order Claude →
OpenAI → Gemini → Pioneer; otherwise Mock. The chosen primary is always wrapped
with a resilient Mock fallback, so callers get uniform timeout/retry/fallback
behavior and the demo never depends on an external service.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.providers.llm.base import LLMProvider
from app.providers.llm.mock import MockProvider
from app.providers.llm.resilient import ResilientProvider

# Priority order for "auto" mode.
_AUTO_ORDER = ("claude", "openai", "gemini", "pioneer")


def _build(kind: str, settings: Settings, timeout_s: float) -> LLMProvider | None:
    """Instantiate a provider if its key is configured; None otherwise."""
    try:
        if kind == "claude" and settings.anthropic_api_key:
            from app.providers.llm.claude import ClaudeProvider

            return ClaudeProvider(settings.anthropic_api_key, settings.claude_model, timeout_s=timeout_s)
        if kind == "openai" and settings.openai_api_key:
            from app.providers.llm.openai import OpenAIProvider

            return OpenAIProvider(settings.openai_api_key, settings.openai_model, timeout_s=timeout_s)
        if kind == "gemini" and settings.gemini_api_key:
            from app.providers.llm.gemini import GeminiProvider

            return GeminiProvider(settings.gemini_api_key, settings.gemini_model, timeout_s=timeout_s)
        if kind == "pioneer" and settings.pioneer_api_key:
            from app.providers.llm.pioneer import PioneerProvider

            return PioneerProvider(settings.pioneer_api_key, settings.pioneer_model,
                                   base_url=settings.pioneer_base_url,
                                   adaptive=settings.pioneer_adaptive, timeout_s=timeout_s)
    except Exception:  # noqa: BLE001 — any setup failure degrades to Mock
        return None
    return None


def _select_primary(settings: Settings, timeout_s: float) -> LLMProvider:
    pref = settings.llm_provider
    if pref in _AUTO_ORDER:
        return _build(pref, settings, timeout_s) or MockProvider()
    if pref == "mock":
        return MockProvider()
    # auto
    for kind in _AUTO_ORDER:
        provider = _build(kind, settings, timeout_s)
        if provider is not None:
            return provider
    return MockProvider()


def get_provider() -> LLMProvider:
    settings = get_settings()
    timeout_s = settings.llm_timeout_ms / 1000.0
    primary = _select_primary(settings, timeout_s)
    return ResilientProvider(primary, MockProvider(), timeout_s=timeout_s, max_retries=settings.llm_max_retries)
