"""Idempotent, concurrency-safe execution engine.

One lock serializes execution per engine; executions are keyed by idempotency_key.
- A key that already reached EXECUTED never runs again → ``prevented=True`` (the
  original execution is returned unchanged).
- Concurrent approvals serialize on the lock: the first executes, the rest are
  prevented — so two approvals can never execute twice.
- A FAILED attempt drops its key so a later retry can re-attempt safely (no
  successful side effect occurred), without ever duplicating a successful one.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from app.sentinel.actions.provider import ProviderMode, SecurityActionProvider
from app.sentinel.enums import ActionExecutionStatus, ActionProvider, SecurityActionType
from app.sentinel.models import ActionExecution


def _now() -> datetime:
    return datetime.now(UTC)


class ExecutionEngine:
    def __init__(self, provider: SecurityActionProvider) -> None:
        self._provider = provider
        self._lock = threading.Lock()
        self._by_key: dict[str, ActionExecution] = {}

    def mode(self) -> ProviderMode:
        return self._provider.mode()

    def execute(
        self,
        *,
        idempotency_key: str,
        incident_id: str,
        action_id: str,
        action_type: SecurityActionType,
        channel: ActionProvider,
        params: dict | None = None,
    ) -> tuple[ActionExecution, bool]:
        """Return ``(execution, prevented)``. ``prevented`` is True when a prior
        successful execution for this key already exists (no duplicate run)."""
        with self._lock:
            existing = self._by_key.get(idempotency_key)
            if existing is not None and existing.status in (
                ActionExecutionStatus.EXECUTED, ActionExecutionStatus.EXECUTING
            ):
                return existing, True

            execution = ActionExecution(
                incident_id=incident_id, action_id=action_id, provider=channel,
                status=ActionExecutionStatus.EXECUTING, idempotency_key=idempotency_key,
                started_at=_now(),
            )
            self._by_key[idempotency_key] = execution

            try:
                outcome = self._provider.execute(action_type, incident_id, params or {}, idempotency_key)
                ok, error, result = outcome.ok, outcome.error, outcome.result
            except Exception as exc:  # noqa: BLE001 — timeout/provider error → FAILED, never crash
                ok, error, result = False, type(exc).__name__, {}

            execution.completed_at = _now()
            if ok:
                execution.status = ActionExecutionStatus.EXECUTED
                execution.result = result
            else:
                execution.status = ActionExecutionStatus.FAILED
                execution.error = error
                # Safe retry: no successful side effect, so free the key for re-attempt.
                self._by_key.pop(idempotency_key, None)
            return execution, False
