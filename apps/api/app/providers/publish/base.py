"""The publish provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class PublishProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def publish(self, title: str, markdown: str, meta: dict | None = None) -> str | None:
        """Publish the content; return a public URL, or None if not published."""
