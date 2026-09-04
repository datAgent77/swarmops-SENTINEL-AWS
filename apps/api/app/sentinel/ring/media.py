"""Optional media retrieval — snapshots via the documented image-download endpoint.

Media is ALWAYS optional. Any failure (snapshot unavailable, no subscription,
privacy config, timeout, network error) returns ``None`` and never raises, so
incident processing continues on metadata alone. Returns an opaque handle, never
a sensitive media URL, and logs nothing sensitive.
"""

from __future__ import annotations

from typing import Protocol


class MediaAdapter(Protocol):
    def get_snapshot_reference(self, device_id: str, component_id: str | None = None) -> str | None: ...


class NullMediaAdapter:
    """Metadata-only: no media source configured/available."""

    def get_snapshot_reference(self, device_id: str, component_id: str | None = None) -> str | None:
        return None


class RingMediaAdapter:
    """Best-effort snapshot handle via ``POST /v1/devices/{id}/media/image/download``.

    The concrete HTTP call is intentionally guarded: on ANY error it degrades to
    metadata-only (returns None). A real client is injected in production; absent
    one, it stays metadata-only.
    """

    def __init__(self, http_call=None) -> None:  # http_call: (device_id, component_id) -> handle
        self._http_call = http_call

    def get_snapshot_reference(self, device_id: str, component_id: str | None = None) -> str | None:
        if self._http_call is None:
            return None
        try:
            return self._http_call(device_id, component_id)
        except Exception:  # noqa: BLE001 — media failure must never break processing
            return None
