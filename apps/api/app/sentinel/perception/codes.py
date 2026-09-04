"""The fixed vocabulary of observation codes the perceiver may emit."""

from __future__ import annotations

VALID_OBSERVATION_CODES: frozenset[str] = frozenset({
    "PERSON_PRESENT",
    "VEHICLE_PRESENT",
    "PACKAGE_PRESENT",
    "PROLONGED_ENTRANCE_ACTIVITY",
    "REPEATED_ACTIVITY",
    "DELIVERY_LIKELY",
    "VISIBILITY_LOW",
    "NO_RELEVANT_ACTIVITY",
})


def filter_codes(codes: list[str]) -> list[str]:
    """Keep only known codes, de-duplicated and order-stable. Unknown codes are
    dropped (never trusted), which keeps a chatty model from injecting semantics."""
    seen: dict[str, None] = {}
    for code in codes:
        if isinstance(code, str) and code in VALID_OBSERVATION_CODES and code not in seen:
            seen[code] = None
    return list(seen)
