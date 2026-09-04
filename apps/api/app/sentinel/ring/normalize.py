"""Normalize a documented Ring webhook payload into a Sentinel ``SecurityEvent``.

Mapping (Ring → Sentinel):

    data.type              -> provider_event_type + SecurityEventType
    data.id                -> device_id
    data.attributes.sub_type      -> motion_type (e.g. "human"|"package"|"vehicle")
    data.attributes.component_ids -> component_id (first, if present)
    meta.request_id        -> provider_event_id (stable id for dedup)
    meta.timestamp (ms)    -> occurred_at (UTC)
    sha256(raw_body)       -> raw_metadata_hash (audit; carries no PII/URLs)
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.sentinel.enums import SecurityEventType
from app.sentinel.models import SecurityEvent
from app.sentinel.ring.base import RingWebhookEnvelope

PROVIDER = "ring"

# Documented Ring event types → Sentinel event types.
_TYPE_MAP: dict[str, SecurityEventType] = {
    "motion_detected": SecurityEventType.MOTION,
    "button_press": SecurityEventType.DOORBELL_PRESS,
    "device_online": SecurityEventType.DEVICE_ONLINE,
    "device_offline": SecurityEventType.DEVICE_OFFLINE,
}


def _timestamp_to_dt(ms: int | None) -> datetime:
    if ms is None:
        return datetime.now(UTC)
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


def normalize_ring_event(
    envelope: RingWebhookEnvelope,
    raw_body: bytes,
    *,
    location_id: str,
    signature_verified: bool,
    media_reference: str | None = None,
    provider: str = PROVIDER,
) -> SecurityEvent:
    data = envelope.data
    attrs = data.attributes or {}
    component_ids = attrs.get("component_ids") or []
    component_id = str(component_ids[0]) if component_ids else None
    sub_type = attrs.get("sub_type")

    return SecurityEvent(
        location_id=location_id,
        device_id=data.id,
        type=_TYPE_MAP.get(data.type, SecurityEventType.OTHER),
        occurred_at=_timestamp_to_dt(envelope.meta.timestamp),
        signature_verified=signature_verified,
        provider=provider,
        provider_event_id=envelope.meta.request_id,
        provider_event_type=data.type,
        component_id=component_id,
        motion_type=str(sub_type) if sub_type is not None else None,
        media_reference=media_reference,
        raw_metadata_hash=hashlib.sha256(raw_body).hexdigest(),
        metadata={"account_id": envelope.meta.account_id} if envelope.meta.account_id else {},
    )
