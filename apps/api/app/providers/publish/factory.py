"""Publisher selection. cited.md when a CITED_API_KEY is configured, else local."""

from __future__ import annotations

from app.config import get_settings
from app.providers.publish.base import PublishProvider
from app.providers.publish.local import LocalPublisher


def get_publisher() -> PublishProvider:
    settings = get_settings()
    if settings.cited_api_key:
        try:
            from app.providers.publish.cited import CitedPublisher

            return CitedPublisher(api_key=settings.cited_api_key, base_url=settings.cited_base_url)
        except Exception:  # noqa: BLE001 — any setup failure degrades to local
            return LocalPublisher()
    return LocalPublisher()
