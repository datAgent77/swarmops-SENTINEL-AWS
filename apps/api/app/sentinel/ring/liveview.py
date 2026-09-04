"""Isolated live-view (WebRTC/WHEP) adapter.

Deliberately decoupled from incident processing: creating or failing a live
session must never affect detection, assessment, or governance. Wraps the
documented WHEP endpoints
(``POST /v1/devices/{id}/media/streaming/whep/sessions``). No live client is wired
in this phase; the adapter exists as a clean seam.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WhepSession:
    session_id: str
    device_id: str
    sdp_answer: str | None = None


class RingLiveViewAdapter:
    """Best-effort WHEP session management, isolated from core processing."""

    def __init__(self, http_call=None) -> None:  # http_call: (device_id, sdp_offer) -> WhepSession
        self._http_call = http_call

    def available(self) -> bool:
        return self._http_call is not None

    def create_session(self, device_id: str, sdp_offer: str) -> WhepSession | None:
        if self._http_call is None:
            return None
        try:
            return self._http_call(device_id, sdp_offer)
        except Exception:  # noqa: BLE001 — live view is never on the critical path
            return None
