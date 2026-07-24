"""LLM provider interface and transport types.

All providers speak the same request/response shape. A response always reports
token usage, provider/model identity, and latency so the orchestrator can track
and display cost — regardless of which provider actually served the call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMRequest:
    system_prompt: str
    user_prompt: str
    temperature: float = 0.4
    max_tokens: int = 1024
    # A hint identifying the expected structured schema (e.g. "ceo", "pm").
    # Providers that generate freely (Gemini) put this in the prompt; the
    # deterministic MockProvider uses it to select a canned structured reply.
    schema_name: str | None = None
    # Extra structured context the MockProvider may interpolate (objective, etc.).
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str
    usage: LLMUsage
    provider: str
    model: str
    latency_ms: int
    raw: Any = None


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) for providers that don't report usage."""
    return max(1, len(text) // 4)


class LLMProvider(ABC):
    """The only abstraction business logic depends on."""

    name: str = "base"
    model: str = "base"

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a completion. Implementations must populate usage/provider/latency."""
        raise NotImplementedError

    async def aclose(self) -> None:  # optional cleanup hook
        return None
