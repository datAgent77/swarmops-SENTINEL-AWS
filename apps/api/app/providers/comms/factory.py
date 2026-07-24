"""Comms selection. Band when a BAND_API_KEY is configured, else a local no-op."""

from __future__ import annotations

from app.config import get_settings
from app.providers.comms.base import CommsProvider
from app.providers.comms.local import LocalComms


def get_comms() -> CommsProvider:
    settings = get_settings()
    if settings.band_api_key:
        try:
            from app.providers.comms.band import BandComms

            return BandComms(
                api_key=settings.band_api_key,
                base_url=settings.band_base_url,
                agent_id=settings.band_agent_id,
                chat_id=settings.band_chat_id,
            )
        except Exception:  # noqa: BLE001 — any setup failure degrades to local
            return LocalComms()
    return LocalComms()
