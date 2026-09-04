"""Idempotent event de-duplication.

Ring retries deliveries and expects idempotency keyed on ``meta.request_id``. We
prefer the provider event id; if absent, a stable SHA-256 fingerprint of the raw
payload is used. Bounded memory (FIFO) so a long-running process cannot grow
without limit — durable dedup moves to the database in P03.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict


def fingerprint(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


class EventDeduplicator:
    def __init__(self, capacity: int = 10_000) -> None:
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._capacity = capacity

    def is_new(self, key: str) -> bool:
        """Return True and remember ``key`` if unseen; False if it is a duplicate."""
        if key in self._seen:
            self._seen.move_to_end(key)
            return False
        self._seen[key] = None
        if len(self._seen) > self._capacity:
            self._seen.popitem(last=False)
        return True

    def key_for(self, provider_event_id: str | None, raw_body: bytes) -> str:
        return provider_event_id or fingerprint(raw_body)
