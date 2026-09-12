"""Security action provider abstraction + demo implementation.

A provider DELIVERS an officer action over its own channel (owner app, security
team, internal note). It is deliberately NOT Ring: Sentinel never claims Ring
performs an unsupported physical action. GRANT_TEMPORARY_ACCESS is not a supported
delivery action here — it stays governed by policy (DENY) upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from app.sentinel.enums import SecurityActionType

# Actions a delivery provider may actually perform.
SUPPORTED_ACTIONS: frozenset[SecurityActionType] = frozenset({
    SecurityActionType.NOTIFY_OWNER,
    SecurityActionType.SEND_WARNING,
    SecurityActionType.NOTIFY_SECURITY,
    SecurityActionType.CREATE_INCIDENT_NOTE,
    SecurityActionType.REQUEST_LIVE_REVIEW,
})


class ProviderMode(str, Enum):
    CONNECTED = "CONNECTED"
    DEMO_MODE = "DEMO_MODE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ERROR = "ERROR"


@dataclass
class ExecutionOutcome:
    ok: bool
    provider: str
    provider_mode: ProviderMode
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class UnsupportedActionError(Exception):
    """The provider does not deliver this action (e.g. a physical control)."""


@runtime_checkable
class SecurityActionProvider(Protocol):
    name: str

    def mode(self) -> ProviderMode: ...

    def execute(self, action_type: SecurityActionType, incident_id: str,
                params: dict[str, Any], idempotency_key: str) -> ExecutionOutcome: ...


class DemoSecurityActionProvider:
    """Deterministic demo delivery. No real external calls; never touches Ring.

    Test hooks: ``fail_times`` makes the next N executions fail (for safe-retry and
    failure-state tests); ``raise_timeout`` makes those failures raise TimeoutError.
    """

    name = "demo-action-provider"

    def __init__(self, *, fail_times: int = 0, raise_timeout: bool = False) -> None:
        self._remaining_failures = fail_times
        self._raise_timeout = raise_timeout

    def mode(self) -> ProviderMode:
        return ProviderMode.DEMO_MODE

    def execute(self, action_type: SecurityActionType, incident_id: str,
                params: dict[str, Any], idempotency_key: str) -> ExecutionOutcome:
        if action_type not in SUPPORTED_ACTIONS:
            # Never fake an unsupported (e.g. physical) action.
            raise UnsupportedActionError(action_type.value)

        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            if self._raise_timeout:
                raise TimeoutError("provider timed out")
            return ExecutionOutcome(ok=False, provider=self.name, provider_mode=self.mode(),
                                    error="provider_error")

        return ExecutionOutcome(
            ok=True, provider=self.name, provider_mode=self.mode(),
            result={"delivered": True, "action": action_type.value, "incident_id": incident_id},
        )
