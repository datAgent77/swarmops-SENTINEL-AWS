"""P07 tests: guided demo runs deterministically across consecutive runs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_status_reports_all_four_providers(client):
    body = client.get("/api/sentinel/status").json()
    assert body["on_duty"] is True
    assert body["location"] == "SaitALCorp Office"
    p = body["providers"]
    assert p["swarmops"]["status"] == "ACTIVE"
    assert p["alexa_mcp"]["status"] == "READY"
    assert p["alexa_mcp"]["tools"] == 8
    assert p["ring"]["status"] in {"DEMO_MODE", "CONNECTED", "NOT_CONFIGURED", "ERROR"}
    assert p["bedrock"]["status"] in {"DEMO_MODE", "CONNECTED"}


def _run_full_demo(client) -> dict:
    start = client.post("/api/sentinel/demo/start").json()

    # Ring events really entered the backend, signed and verified.
    assert len(start["ring_events"]) == 3
    assert all(e["signature_verified"] for e in start["ring_events"])

    # Centerpiece: AI recommends GRANT, deterministic policy DENIES with the reasons.
    cp = start["centerpiece"]
    assert cp["ai_recommendation"] == "GRANT_TEMPORARY_ACCESS"
    assert cp["decision"] == "DENY"
    for code in ("OUTSIDE_BUSINESS_HOURS", "NO_VERIFIED_VISITOR",
                 "NO_APPROVED_ACCESS_REQUEST", "NO_VALID_CREDENTIAL", "RISK_TOO_HIGH"):
        assert code in cp["reason_codes"]

    # Second action requires human approval.
    sa = start["second_action"]
    assert sa["decision"] == "REQUIRE_APPROVAL"
    approval_id = sa["approval_id"]
    incident_id = start["incident_id"]

    # Human approves → executes.
    approved = client.post("/api/sentinel/approve", json={
        "incident_id": incident_id, "approval_id": approval_id, "actor_id": "officer-sam",
    }).json()
    assert approved["executed"] is True

    # Replay the exact same request → duplicate execution prevented.
    replay = client.post("/api/sentinel/propose", json={
        "incident_id": incident_id, "action_type": "SEND_WARNING",
        "actor_id": "owner-alex", "action_request_id": sa["action_request_id"],
    }).json()
    assert replay["duplicate_prevented"] is True
    return start


def test_guided_demo_is_deterministic_across_consecutive_runs(client):
    client.post("/api/sentinel/demo/reset")
    first = _run_full_demo(client)
    for _ in range(3):
        again = _run_full_demo(client)
        assert again["centerpiece"]["reason_codes"] == first["centerpiece"]["reason_codes"]
        assert again["incident"]["risk"]["risk_level"] == first["incident"]["risk"]["risk_level"]


def test_reset_only_clears_demo_state(client):
    client.post("/api/sentinel/demo/start")
    assert client.post("/api/sentinel/demo/reset").json()["ok"] is True
    # Base demo incident is available again after reset.
    assert client.get("/api/sentinel/incident").status_code == 200


def test_wrong_role_cannot_approve_via_rest(client):
    start = client.post("/api/sentinel/demo/start").json()
    resp = client.post("/api/sentinel/approve", json={
        "incident_id": start["incident_id"],
        "approval_id": start["second_action"]["approval_id"],
        "actor_id": "guest-01",
    })
    assert resp.status_code == 403  # SwarmOps blocks the bypass
