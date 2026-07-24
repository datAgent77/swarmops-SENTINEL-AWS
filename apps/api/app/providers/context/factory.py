"""Context selection. Senso when a SENSO_API_KEY is configured, else local no-op."""

from __future__ import annotations

from app.config import get_settings
from app.providers.context.base import ContextProvider
from app.providers.context.local import LocalContext


def get_context() -> ContextProvider:
    settings = get_settings()
    if settings.senso_api_key:
        try:
            from app.providers.context.senso import SensoContext

            return SensoContext(api_key=settings.senso_api_key, base_url=settings.senso_base_url)
        except Exception:  # noqa: BLE001 — any setup failure degrades to local
            return LocalContext()
    return LocalContext()
