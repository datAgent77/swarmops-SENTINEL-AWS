"""P02 tests: Ring sensing layer (normalization, dedup, auth, media, correlation)."""

from __future__ import annotations

import pytest

from app.sentinel.enums import IncidentStatus, SecurityEventType
from app.sentinel.ring.base import ProviderStatus
from app.sentinel.ring.developer import RingDeveloperProvider
from app.sentinel.ring.ingest import RingIngestService
from app.sentinel.ring.media import NullMediaAdapter, RingMediaAdapter
from app.sentinel.ring.mock import MockRingProvider
from app.sentinel.ring.simulator import RingSimulatorProvider
from app.sentinel.ring.webhook import sign_body, verify_signature

SECRET = "test-ring-secret"
T0 = 1_770_000_000_000  # fixed epoch ms


def _service() -> tuple[RingSimulatorProvider, RingIngestService]:
    sim = RingSimulatorProvider(SECRET)
    return sim, RingIngestService(sim)


# --- normalization: MOTION / PACKAGE / VEHICLE --------------------------------

@pytest.mark.parametrize(
    "event_type,expected_motion",
    [("MOTION", "human"), ("PACKAGE", "package"), ("VEHICLE", "vehicle")],
)
def test_normalizes_ring_smart_detection(event_type, expected_motion):
    sim, svc = _service()
    raw, sig = sim.build_event(event_type, "ring-front-door")
    result = svc.ingest_webhook(raw, sig)

    assert result.accepted is True
    ev = result.event
    assert ev is not None
    assert ev.provider == "ring"
    assert ev.provider_event_type == "motion_detected"
    assert ev.type is SecurityEventType.MOTION
    assert ev.motion_type == expected_motion
    assert ev.signature_verified is True
    assert ev.raw_metadata_hash and len(ev.raw_metadata_hash) == 64
    assert "ring_event_received" in [a.action for a in result.audits]


def test_normalizes_button_press():
    sim, svc = _service()
    raw, sig = sim.build_event("DOORBELL", "ring-front-door")
    result = svc.ingest_webhook(raw, sig)
    assert result.event.type is SecurityEventType.DOORBELL_PRESS
    assert result.event.provider_event_type == "button_press"


# --- signature verification ---------------------------------------------------

def test_signature_roundtrip_and_tamper():
    body = b'{"hello":"ring"}'
    sig = sign_body(body, SECRET)
    assert verify_signature(body, sig, SECRET) is True
    assert verify_signature(body + b"x", sig, SECRET) is False   # tampered body
    assert verify_signature(body, sig, "wrong") is False         # wrong secret
    assert verify_signature(body, None, SECRET) is False         # missing header
    assert verify_signature(body, "md5=abc", SECRET) is False    # wrong scheme


def test_invalid_signature_is_rejected_and_audited():
    sim, svc = _service()
    raw, sig = sim.build_event("MOTION", "d1")
    result = svc.ingest_webhook(raw + b"tamper", sig)
    assert result.accepted is False
    assert result.reason == "invalid_signature"
    assert "ring_signature_rejected" in [a.action for a in result.audits]


def test_missing_signature_is_rejected():
    sim, svc = _service()
    raw, _ = sim.build_event("MOTION", "d1")
    result = svc.ingest_webhook(raw, None)
    assert result.accepted is False and result.reason == "invalid_signature"


# --- invalid payload ----------------------------------------------------------

def test_signed_but_malformed_payload_rejected():
    _, svc = _service()
    body = b"not-json-at-all"
    result = svc.ingest_webhook(body, sign_body(body, SECRET))
    assert result.accepted is False and result.reason == "invalid_payload"
    assert "ring_event_invalid" in [a.action for a in result.audits]


def test_signed_json_missing_envelope_fields_rejected():
    _, svc = _service()
    body = b'{"foo":"bar"}'  # valid JSON, not a Ring envelope
    result = svc.ingest_webhook(body, sign_body(body, SECRET))
    assert result.accepted is False and result.reason == "invalid_payload"


# --- deduplication ------------------------------------------------------------

def test_duplicate_delivery_is_deduplicated():
    sim, svc = _service()
    raw, sig = sim.build_event("MOTION", "d1", request_id="req-123")
    first = svc.ingest_webhook(raw, sig)
    second = svc.ingest_webhook(raw, sig)
    assert first.accepted is True and first.duplicate is False
    assert second.accepted is False and second.duplicate is True
    assert "ring_event_deduplicated" in [a.action for a in second.audits]


# --- provider status ----------------------------------------------------------

def test_developer_provider_not_configured_without_keys():
    dev = RingDeveloperProvider(client_id=None, client_secret=None, webhook_secret=None)
    assert dev.info().status is ProviderStatus.NOT_CONFIGURED


def test_developer_provider_connected_only_after_verified_event():
    dev = RingDeveloperProvider(client_id="c", client_secret="s", webhook_secret="w")
    # Configured but unproven → not a green connection yet.
    assert dev.info().status is ProviderStatus.NOT_CONFIGURED
    raw = b'{"meta":{"request_id":"r"},"data":{"type":"motion_detected","id":"d","attributes":{}}}'
    assert dev.verify_signature(raw, sign_body(raw, "w")) is True
    assert dev.info().status is ProviderStatus.CONNECTED


def test_simulator_is_demo_mode():
    assert RingSimulatorProvider(SECRET).info().status is ProviderStatus.DEMO_MODE


def test_provider_unavailable_rejects_events():
    svc = RingIngestService(MockRingProvider(status=ProviderStatus.ERROR, accept_signatures=False))
    sim = RingSimulatorProvider(SECRET)
    result = svc.ingest_webhook(*sim.build_event("MOTION", "d1"))
    assert result.accepted is False and result.reason == "invalid_signature"
    assert svc.info().status is ProviderStatus.ERROR


# --- media optionality --------------------------------------------------------

def test_media_metadata_only_by_default():
    sim, svc = _service()
    result = svc.ingest_webhook(*sim.build_event("MOTION", "d1"))
    assert result.accepted is True
    assert result.event.media_reference is None  # NullMediaAdapter


def test_media_failure_never_breaks_processing():
    sim = RingSimulatorProvider(SECRET)

    def boom(device_id, component_id=None):
        raise TimeoutError("snapshot timed out")

    svc = RingIngestService(sim, media=RingMediaAdapter(http_call=boom))
    result = svc.ingest_webhook(*sim.build_event("MOTION", "d1"))
    assert result.accepted is True
    assert result.event.media_reference is None  # degraded to metadata-only


def test_media_reference_attached_when_available():
    sim = RingSimulatorProvider(SECRET)
    svc = RingIngestService(
        sim, media=RingMediaAdapter(http_call=lambda d, c=None: "snapshot-handle-1")
    )
    result = svc.ingest_webhook(*sim.build_event("MOTION", "d1"))
    assert result.event.media_reference == "snapshot-handle-1"
    assert isinstance(NullMediaAdapter().get_snapshot_reference("d1"), type(None))


# --- incident creation + correlation ------------------------------------------

def test_single_event_creates_one_incident():
    sim, svc = _service()
    result = svc.ingest_webhook(*sim.build_event("MOTION", "d1", timestamp_ms=T0, request_id="a"))
    inc = result.incident
    assert inc is not None
    assert inc.status is IncidentStatus.DETECTED
    assert len(inc.event_ids) == 1


def test_three_events_within_window_correlate_into_one_incident():
    sim, svc = _service()
    r1 = svc.ingest_webhook(*sim.build_event("MOTION", "d1", timestamp_ms=T0, request_id="a"))
    r2 = svc.ingest_webhook(*sim.build_event("MOTION", "d1", timestamp_ms=T0 + 120_000, request_id="b"))
    r3 = svc.ingest_webhook(*sim.build_event("MOTION", "d1", timestamp_ms=T0 + 300_000, request_id="c"))
    assert r2.incident.incident_id == r1.incident.incident_id
    assert r3.incident.incident_id == r1.incident.incident_id
    assert len(r3.incident.event_ids) == 3


def test_events_beyond_window_start_a_new_incident():
    sim, svc = _service()
    r1 = svc.ingest_webhook(*sim.build_event("MOTION", "d1", timestamp_ms=T0, request_id="a"))
    r2 = svc.ingest_webhook(
        *sim.build_event("MOTION", "d1", timestamp_ms=T0 + 1_800_000, request_id="b")  # +30 min
    )
    assert r2.incident.incident_id != r1.incident.incident_id


def test_different_devices_do_not_merge():
    sim, svc = _service()
    r1 = svc.ingest_webhook(*sim.build_event("MOTION", "d1", timestamp_ms=T0, request_id="a"))
    r2 = svc.ingest_webhook(*sim.build_event("MOTION", "d2", timestamp_ms=T0, request_id="b"))
    assert r1.incident.incident_id != r2.incident.incident_id


# --- API surface: a documented Ring event entering the backend at runtime ------

def test_api_status_and_simulate_end_to_end():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.sentinel.ring.factory import reset_ingest_service

    reset_ingest_service()  # isolate in-memory dedup/correlation state
    client = TestClient(app)

    status = client.get("/api/ring/status").json()
    assert status["provider"] in {"ring", "ring-simulator"}
    assert status["status"] in {"DEMO_MODE", "CONNECTED", "NOT_CONFIGURED", "ERROR"}

    resp = client.post(
        "/api/ring/simulate", json={"event_type": "PACKAGE", "device_id": "ring-front-door"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["event"]["provider"] == "ring"
    assert body["event"]["motion_type"] == "package"
    assert body["event"]["signature_verified"] is True
    assert body["incident"]["event_count"] >= 1
    assert "ring_event_received" in body["audit"]
    reset_ingest_service()


def test_api_rejects_unsigned_webhook():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.sentinel.ring.factory import reset_ingest_service

    reset_ingest_service()
    client = TestClient(app)
    resp = client.post("/api/ring/webhook", content=b'{"meta":{"request_id":"x"}}')
    assert resp.status_code == 401  # no X-Signature → rejected, never processed
    reset_ingest_service()
