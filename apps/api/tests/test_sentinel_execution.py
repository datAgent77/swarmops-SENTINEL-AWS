"""P06 tests: governed action execution — idempotency, concurrency, audit."""

from __future__ import annotations

import threading

import pytest

from app.sentinel.actions.engine import ExecutionEngine
from app.sentinel.actions.provider import (
    DemoSecurityActionProvider,
    ProviderMode,
    UnsupportedActionError,
)
from app.sentinel.enums import ActionExecutionStatus, ActionProvider, SecurityActionType
from app.sentinel.officer.service import OfficerService

A = SecurityActionType


def _svc(provider=None) -> tuple[OfficerService, str]:
    svc = OfficerService(action_provider=provider)
    return svc, svc.seed_demo_incident("inc-exec")


# --- provider: never fakes an unsupported (physical) action --------------------

def test_provider_refuses_unsupported_action():
    provider = DemoSecurityActionProvider()
    assert provider.mode() is ProviderMode.DEMO_MODE
    with pytest.raises(UnsupportedActionError):
        provider.execute(A.GRANT_TEMPORARY_ACCESS, "inc", {}, "k")


def test_provider_delivers_supported_action():
    outcome = DemoSecurityActionProvider().execute(A.SEND_WARNING, "inc", {}, "k")
    assert outcome.ok is True
    assert outcome.result["delivered"] is True


# --- engine idempotency + concurrency ----------------------------------------

def _exec(engine, key="k1"):
    return engine.execute(idempotency_key=key, incident_id="i", action_id="a",
                          action_type=A.SEND_WARNING, channel=ActionProvider.SECURITY_TEAM)


def test_engine_duplicate_execution_prevented():
    engine = ExecutionEngine(DemoSecurityActionProvider())
    e1, prev1 = _exec(engine)
    e2, prev2 = _exec(engine)
    assert prev1 is False and e1.status is ActionExecutionStatus.EXECUTED
    assert prev2 is True
    assert e2.execution_id == e1.execution_id  # original remains the only execution


def test_engine_parallel_executes_once():
    engine = ExecutionEngine(DemoSecurityActionProvider())
    results: list[tuple] = []

    def worker() -> None:
        results.append(_exec(engine))

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    not_prevented = [e for e, prev in results if not prev]
    assert len(not_prevented) == 1                       # exactly one real execution
    assert len({e.execution_id for e, _ in results}) == 1


def test_engine_timeout_becomes_failed():
    engine = ExecutionEngine(DemoSecurityActionProvider(fail_times=1, raise_timeout=True))
    execution, prevented = _exec(engine)
    assert prevented is False
    assert execution.status is ActionExecutionStatus.FAILED
    assert execution.error == "TimeoutError"


def test_engine_safe_retry_after_failure():
    engine = ExecutionEngine(DemoSecurityActionProvider(fail_times=1))  # first fails, then ok
    first, _ = _exec(engine)
    second, _ = _exec(engine)
    assert first.status is ActionExecutionStatus.FAILED
    assert second.status is ActionExecutionStatus.EXECUTED   # retry succeeds, no dup


# --- pipeline via the officer service -----------------------------------------

def test_deny_never_executes():
    svc, iid = _svc()
    res = svc.propose(iid, "GRANT_TEMPORARY_ACCESS", "owner-alex", action_request_id="g1")
    assert res["decision"] == "DENY"
    assert res["executed"] is False
    assert svc.action_status(iid, res["action_id"])["execution"] is None


def test_approval_required_blocks_then_allows_execution():
    svc, iid = _svc()
    proposed = svc.propose(iid, "SEND_WARNING", "owner-alex", action_request_id="w1")
    assert proposed["executed"] is False                      # blocked pending approval
    approved = svc.approve(iid, proposed["approval_id"], "officer-sam")
    assert approved["executed"] is True
    status = svc.action_status(iid, proposed["action_id"])
    assert status["execution"]["status"] == "EXECUTED"


def test_idempotent_propose_same_request_reuses_action():
    svc, iid = _svc()
    a = svc.propose(iid, "SEND_WARNING", "owner-alex", action_request_id="w1")
    b = svc.propose(iid, "SEND_WARNING", "owner-alex", action_request_id="w1")
    assert a["action_id"] == b["action_id"]                   # same logical request

def test_failure_state_when_provider_fails():
    svc, iid = _svc(provider=DemoSecurityActionProvider(fail_times=1))
    res = svc.propose(iid, "NOTIFY_OWNER", "owner-alex", action_request_id="n1")  # ALLOW
    assert res["executed"] is False
    assert svc.action_status(iid, res["action_id"])["execution"]["status"] == "FAILED"


# --- WINNER PROOF: same request twice → duplicate prevented -------------------

def test_winner_proof_duplicate_execution_prevented():
    svc = OfficerService()
    proof = svc.winner_proof()
    assert proof["duplicate_prevented"] is True
    assert proof["executed_count"] == 1                       # original is the only execution
    assert proof["second_execution_id"] == proof["first_execution_id"]
    events = [e["action"] for e in proof["timeline"]]
    assert "execution_completed" in events
    assert "duplicate_execution_prevented" in events


# --- audit completeness + append-only ----------------------------------------

def test_audit_completeness():
    svc = OfficerService()
    events = [e["action"] for e in svc.winner_proof()["timeline"]]
    for required in ("incident_created", "observation_generated", "risk_calculated",
                     "policy_evaluated", "action_proposed", "approval_requested",
                     "approval_granted", "execution_started", "execution_completed",
                     "duplicate_execution_prevented"):
        assert required in events, f"missing audit event: {required}"


def test_audit_is_append_only():
    svc, iid = _svc()
    before = svc.timeline(iid)
    proposed = svc.propose(iid, "SEND_WARNING", "owner-alex", action_request_id="w1")
    svc.approve(iid, proposed["approval_id"], "officer-sam")
    after = svc.timeline(iid)
    assert len(after) > len(before)
    # Earlier records are unchanged (append-only, never mutated or removed).
    assert after[: len(before)] == before


def test_audit_carries_trace_and_idempotency_metadata():
    svc, iid = _svc()
    proposed = svc.propose(iid, "SEND_WARNING", "owner-alex", action_request_id="w1")
    svc.approve(iid, proposed["approval_id"], "officer-sam")
    completed = next(e for e in svc.timeline(iid) if e["action"] == "execution_completed")
    assert completed["metadata"]["idempotency_key"] == "inc-exec:SEND_WARNING:w1"
    assert completed["metadata"]["trace_id"].startswith("trace-")
    assert completed["metadata"]["provider_mode"] == "DEMO_MODE"
