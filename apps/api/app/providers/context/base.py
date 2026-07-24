"""The context provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ContextProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def ingest(self, text: str, source: str, meta: dict | None = None) -> None:
        """Add a piece of content to the shared context store."""

    @abstractmethod
    async def query(self, question: str, k: int = 4) -> str:
        """Retrieve agent-ready context for a question (empty string if none)."""

    async def aclose(self) -> None:  # pragma: no cover - optional cleanup
        return None
