"""LLM provider abstraction.

Business logic never imports a concrete provider (e.g. Gemini) directly — it
depends only on ``LLMProvider`` and obtains an instance via ``get_provider()``.
"""

from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse, LLMUsage
from app.providers.llm.factory import get_provider
from app.providers.llm.mock import MockProvider
from app.providers.llm.resilient import ResilientProvider

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMUsage",
    "MockProvider",
    "ResilientProvider",
    "get_provider",
]
