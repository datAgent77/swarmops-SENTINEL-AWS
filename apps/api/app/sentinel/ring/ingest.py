"""Ring ingestion: verify → parse → dedupe → normalize → correlate.

Turns an authenticated Ring event (real or simulated) into a normalized
``SecurityEvent`` and folds it into a correlated ``SecurityIncident`` using the
P01 windowing rule. Emits audit records (``ring_event_received``,
``ring_event_deduplicated``, ``ring_signature_rejected``, ``ring_event_invalid``).

Correlation is deterministic and AI-free. Incident state is held in memory in
this phase; durable persistence arrives in P03.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.sentinel.enums import TERMINAL_INCIDENT_STATUSES, AuditActorType, IncidentStatus
from app.sentinel.logic import CORRELATION_WINDOW_SECONDS
from app.sentinel.models import AuditEvent, SecurityEvent, SecurityIncident
from app.sentinel.ring.base import ProviderInfo, RingProvider, RingWebhookEnvelope
from app.sentinel.ring.dedupe import EventDeduplicator
from app.sentinel.ring.media import MediaAdapter, NullMediaAdapter
from app.sentinel.ring.normalize import normalize_ring_event


def location_for_device(device_id: str) -> str:
    """Deterministic device → location mapping (a real registry resolves this via
    ``GET /v1/devices/{id}/location`` in production). Same device ⇒ same location,
    so a burst at one entrance correlates into one incident."""
    return f"loc-ring-{device_id}"


@dataclass
class IngestResult:
    accepted: bool
    duplicate: bool = False
    reason: str | None = None
    event: SecurityEvent | None = None
    incident: SecurityIncident | None = None
    audits: list[AuditEvent] = field(default_factory=list)


class IncidentCorrelator:
    """In-memory windowed correlation by EVENT time (deterministic, no AI).

    An event joins the location's open incident when the gap to the last event's
    ``occurred_at`` is within the window (matching the P01 correlation rule).
    """

    def __init__(self, window_seconds: int = CORRELATION_WINDOW_SECONDS) -> None:
        self._window = timedelta(seconds=window_seconds)
        self._open: dict[str, SecurityIncident] = {}
        self._last_at: dict[str, datetime] = {}

    def add(self, event: SecurityEvent) -> SecurityIncident:
        loc = event.location_id
        current = self._open.get(loc)
        last_at = self._last_at.get(loc)
        if (
            current is not None
            and current.status not in TERMINAL_INCIDENT_STATUSES
            and last_at is not None
            and abs((event.occurred_at - last_at).total_seconds()) <= self._window.total_seconds()
        ):
            current.add_event(event)
            self._last_at[loc] = event.occurred_at
            return current
        incident = SecurityIncident(location_id=loc, status=IncidentStatus.DETECTED)
        incident.add_event(event)
        self._open[loc] = incident
        self._last_at[loc] = event.occurred_at
        return incident


class RingIngestService:
    def __init__(
        self,
        provider: RingProvider,
        *,
        media: MediaAdapter | None = None,
        correlator: IncidentCorrelator | None = None,
        deduplicator: EventDeduplicator | None = None,
    ) -> None:
        self._provider = provider
        self._media = media or NullMediaAdapter()
        self._correlator = correlator or IncidentCorrelator()
        self._dedup = deduplicator or EventDeduplicator()

    def info(self) -> ProviderInfo:
        return self._provider.info()

    @staticmethod
    def _audit(action: str, *, reason: str | None = None, incident_id: str | None = None,
               metadata: dict | None = None) -> AuditEvent:
        return AuditEvent(
            incident_id=incident_id, actor_type=AuditActorType.SYSTEM,
            actor_id="ring-intake", action=action, reason=reason, metadata=metadata or {},
        )

    def ingest_webhook(self, raw_body: bytes, signature_header: str | None) -> IngestResult:
        # 1) Authenticity — never trust an unsigned/invalid body.
        if not self._provider.verify_signature(raw_body, signature_header):
            return IngestResult(
                accepted=False, reason="invalid_signature",
                audits=[self._audit("ring_signature_rejected", reason="signature verification failed")],
            )

        # 2) Parse the documented envelope.
        try:
            envelope = RingWebhookEnvelope.model_validate(json.loads(raw_body))
        except Exception:  # noqa: BLE001 — malformed body is rejected, never crashes
            return IngestResult(
                accepted=False, reason="invalid_payload",
                audits=[self._audit("ring_event_invalid", reason="unparseable webhook body")],
            )

        # 3) Idempotency — Ring retries; dedupe on request_id (or a body fingerprint).
        key = self._dedup.key_for(envelope.meta.request_id, raw_body)
        if not self._dedup.is_new(key):
            return IngestResult(
                accepted=False, duplicate=True, reason="duplicate",
                audits=[self._audit("ring_event_deduplicated",
                                    metadata={"provider_event_id": envelope.meta.request_id})],
            )

        # 4) Normalize (+ optional, best-effort media — never fatal).
        location_id = location_for_device(envelope.data.id)
        component_ids = (envelope.data.attributes or {}).get("component_ids") or []
        component_id = str(component_ids[0]) if component_ids else None
        media_reference = self._media.get_snapshot_reference(envelope.data.id, component_id)
        event = normalize_ring_event(
            envelope, raw_body, location_id=location_id,
            signature_verified=True, media_reference=media_reference,
        )

        # 5) Correlate into an incident (deterministic windowing).
        incident = self._correlator.add(event)
        audits = [self._audit(
            "ring_event_received", incident_id=incident.incident_id,
            metadata={"provider_event_type": event.provider_event_type,
                      "device_id": event.device_id, "media": bool(media_reference)},
        )]
        return IngestResult(accepted=True, event=event, incident=incident, audits=audits)
