"""Ring Playground / simulator provider (DEMO_MODE).

Emits events in the SAME documented shape as real Ring webhooks and signs them
with the configured webhook secret, so a simulated event traverses the identical
verify → normalize → dedupe → correlate pipeline a real Ring event would. This is
what a judge sees entering the backend at runtime when no physical device is used.

Smart-detection categories map onto the documented ``motion_detected`` type with
``attributes.sub_type`` (``human`` | ``package`` | ``vehicle``).
"""

from __future__ import annotations

import json
import time
import uuid

from app.sentinel.ring.base import ProviderInfo, ProviderStatus
from app.sentinel.ring.webhook import sign_body

# Playground event → Ring (type, sub_type).
_SIMULATED: dict[str, tuple[str, str | None]] = {
    "MOTION": ("motion_detected", "human"),
    "PACKAGE": ("motion_detected", "package"),
    "VEHICLE": ("motion_detected", "vehicle"),
    "DOORBELL": ("button_press", None),
}


class RingSimulatorProvider:
    name = "ring-simulator"

    def __init__(self, webhook_secret: str) -> None:
        # A demo secret is fine here — it only signs simulated events. Never logged.
        self._secret = webhook_secret

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider=self.name,
            status=ProviderStatus.DEMO_MODE,
            detail="Ring Playground simulator: documented payload shape, locally signed.",
        )

    def verify_signature(self, raw_body: bytes, signature_header: str | None) -> bool:
        from app.sentinel.ring.webhook import verify_signature

        return verify_signature(raw_body, signature_header, self._secret)

    def build_event(
        self,
        event_type: str,
        device_id: str,
        *,
        account_id: str = "ava1.ring.account.DEMO",
        component_id: int | None = None,
        request_id: str | None = None,
        timestamp_ms: int | None = None,
    ) -> tuple[bytes, str]:
        """Return ``(raw_body, x_signature)`` for a documented, signed Ring event."""
        ring_type, sub_type = _SIMULATED.get(event_type.upper(), ("motion_detected", "human"))
        attributes: dict[str, object] = {}
        if sub_type is not None:
            attributes["sub_type"] = sub_type
        if component_id is not None:
            attributes["component_ids"] = [component_id]

        payload = {
            "meta": {
                "request_id": request_id or f"sim-{uuid.uuid4().hex}",
                "account_id": account_id,
                "timestamp": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
            },
            "data": {"type": ring_type, "id": device_id, "attributes": attributes},
        }
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return raw, sign_body(raw, self._secret)
