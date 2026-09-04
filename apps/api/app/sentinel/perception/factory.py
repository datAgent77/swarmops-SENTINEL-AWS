"""Perception provider selection.

``PERCEPTION_PROVIDER``: ``bedrock`` | ``mock`` | ``auto``. ``auto`` uses Bedrock
when it is configured (a model id and boto3 present), otherwise the deterministic
Mock provider so the demo runs with no AWS keys.
"""

from __future__ import annotations

import importlib.util

from app.config import Settings, get_settings
from app.sentinel.perception.base import SecurityPerceptionProvider
from app.sentinel.perception.bedrock import BedrockSecurityPerceptionProvider
from app.sentinel.perception.mock import MockSecurityPerceptionProvider


def _boto3_available() -> bool:
    try:
        return importlib.util.find_spec("boto3") is not None
    except ModuleNotFoundError:
        return False


def bedrock_configured(settings: Settings) -> bool:
    return bool(settings.bedrock_model_id) and _boto3_available()


def build_perception_provider(settings: Settings | None = None) -> SecurityPerceptionProvider:
    settings = settings or get_settings()
    mode = (settings.perception_provider or "auto").lower()
    min_conf = settings.perception_min_confidence

    if mode == "mock":
        return MockSecurityPerceptionProvider(min_confidence=min_conf)
    if mode == "bedrock" or (mode == "auto" and bedrock_configured(settings)):
        return BedrockSecurityPerceptionProvider(
            model_id=settings.bedrock_model_id or "",
            region=settings.bedrock_region,
            timeout_s=settings.perception_timeout_ms / 1000.0,
            min_confidence=min_conf,
        )
    return MockSecurityPerceptionProvider(min_confidence=min_conf)
