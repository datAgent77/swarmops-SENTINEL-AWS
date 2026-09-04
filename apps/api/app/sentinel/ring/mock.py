"""Testing-only Ring provider with controllable behavior.

Lets tests exercise invalid signatures, provider-unavailable, and error states
without any network. Never used outside tests.
"""

from __future__ import annotations

from app.sentinel.ring.base import ProviderInfo, ProviderStatus


class MockRingProvider:
    name = "ring-mock"

    def __init__(
        self,
        *,
        status: ProviderStatus = ProviderStatus.DEMO_MODE,
        accept_signatures: bool = True,
        detail: str = "mock",
    ) -> None:
        self._status = status
        self._accept = accept_signatures
        self._detail = detail

    def info(self) -> ProviderInfo:
        return ProviderInfo(provider=self.name, status=self._status, detail=self._detail)

    def verify_signature(self, raw_body: bytes, signature_header: str | None) -> bool:
        return self._accept and signature_header is not None
