"""P05 tests: authoritative officer service (propose/approve/reject, role + expiry)."""

from __future__ import annotations

import pytest

from app.domain.errors import ConflictError, NotFoundError
from app.sentinel.officer.service import (
    ApprovalExpiredError,
    OfficerService,
    SelfApprovalError,
    WrongRoleError,
)


def _svc() -> tuple[OfficerService, str]:
    svc = OfficerService()
    return svc, svc.seed_demo_incident("inc-test")


# --- read surface -------------------------------------------------------------

def test_get_incident_and_explanation_from_authoritative_state():
    svc, iid = _svc()
    inc = svc.get_incident(iid)
    assert inc["risk"]["risk_level"] == "CRITICAL"

    ex = svc.explain(iid)
    # Derived from state, not invented: the four winner reasons appear.
    joined = " ".join(ex["reasons"]).lower()
    assert "building is closed" in joined
    assert "no verified visitor" in joined or "no visitor is expected" in joined
    assert "no access request exists" in joined
    assert ex["policy_hash"]


def test_allowed_actions_reports_policy_decisions():
    svc, iid = _svc()
    by = {a["action_type"]: a["decision"] for a in svc.allowed_actions(iid)}
    assert by["NOTIFY_OWNER"] == "ALLOW"
    assert by["REQUEST_LIVE_REVIEW"] == "ALLOW"
    assert by["SEND_WARNING"] == "REQUIRE_APPROVAL"
    assert by["NOTIFY_SECURITY"] == "REQUIRE_APPROVAL"
    assert by["GRANT_TEMPORARY_ACCESS"] == "DENY"


# --- propose ------------------------------------------------------------------

def test_propose_allow_executes_immediately():
    svc, iid = _svc()
    res = svc.propose(iid, "NOTIFY_OWNER", "owner-alex")
    assert res["decision"] == "ALLOW"
    assert res["executed"] is True
    assert res["approval_id"] is None


def test_propose_deny_does_not_execute():
    svc, iid = _svc()
    res = svc.propose(iid, "GRANT_TEMPORARY_ACCESS", "owner-alex")
    assert res["decision"] == "DENY"
    assert res["executed"] is False
    status = svc.action_status(iid, res["action_id"])
    assert status["execution"] is None


def test_propose_require_approval_opens_pending_and_does_not_execute():
    svc, iid = _svc()
    res = svc.propose(iid, "SEND_WARNING", "owner-alex")
    assert res["decision"] == "REQUIRE_APPROVAL"
    assert res["approval_id"] is not None
    assert res["executed"] is False  # nothing runs without approval


# --- approve / authority ------------------------------------------------------

def test_approve_by_security_officer_executes_exactly_once():
    svc, iid = _svc()
    res = svc.propose(iid, "SEND_WARNING", "owner-alex")
    out = svc.approve(iid, res["approval_id"], "officer-sam")
    assert out["status"] == "APPROVED"
    assert out["executed"] is True
    exec_id = out["execution_id"]
    # Duplicate approval is idempotent — the action executes exactly once.
    again = svc.approve(iid, res["approval_id"], "officer-sam")
    assert again["execution_id"] == exec_id


def test_wrong_role_cannot_approve():
    svc, iid = _svc()
    res = svc.propose(iid, "SEND_WARNING", "owner-alex")
    with pytest.raises(WrongRoleError):
        svc.approve(iid, res["approval_id"], "guest-01")
    with pytest.raises(WrongRoleError):
        svc.approve(iid, res["approval_id"], "owner-alex")  # owner is not an approver


def test_self_approval_is_forbidden():
    svc, iid = _svc()
    res = svc.propose(iid, "SEND_WARNING", "officer-sam")  # proposer is a security officer
    with pytest.raises(SelfApprovalError):
        svc.approve(iid, res["approval_id"], "officer-sam")
    # A DIFFERENT security officer may approve.
    out = svc.approve(iid, res["approval_id"], "officer-lee")
    assert out["executed"] is True


def test_expired_approval_cannot_be_approved():
    svc, iid = _svc()
    res = svc.propose(iid, "SEND_WARNING", "owner-alex", approval_ttl_seconds=-1)
    with pytest.raises(ApprovalExpiredError):
        svc.approve(iid, res["approval_id"], "officer-sam")


def test_reject_blocks_execution():
    svc, iid = _svc()
    res = svc.propose(iid, "SEND_WARNING", "owner-alex")
    out = svc.reject(iid, res["approval_id"], "officer-sam")
    assert out["status"] == "REJECTED"
    assert svc.action_status(iid, res["action_id"])["execution"] is None
    # Approving a rejected approval conflicts.
    with pytest.raises(ConflictError):
        svc.approve(iid, res["approval_id"], "officer-sam")


def test_unknown_incident_and_approval():
    svc, iid = _svc()
    with pytest.raises(NotFoundError):
        svc.get_incident("nope")
    with pytest.raises(NotFoundError):
        svc.approve(iid, "appr-nope", "officer-sam")


# --- timeline -----------------------------------------------------------------

def test_timeline_records_the_governed_chain():
    svc, iid = _svc()
    res = svc.propose(iid, "SEND_WARNING", "owner-alex")
    svc.approve(iid, res["approval_id"], "officer-sam")
    actions = [e["action"] for e in svc.timeline(iid)]
    assert any(a.startswith("action.proposed") for a in actions)
    assert "approval.requested" in actions
    assert "approval.granted" in actions
    assert any(a.startswith("action.executed") for a in actions)
