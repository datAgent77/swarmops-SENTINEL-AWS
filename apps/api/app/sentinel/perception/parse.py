"""Parse and strictly validate a model's text into a SecurityObservation.

Any authority-shaped key, unknown field, malformed JSON, or schema mismatch raises
``PerceptionSchemaError`` so the caller degrades to a safe UNKNOWN observation —
model output can never smuggle a decision through perception.
"""

from __future__ import annotations

import json
from typing import Any

from app.sentinel.models import _PROHIBITED_OBSERVATION_FIELDS, SecurityObservation
from app.sentinel.perception.codes import filter_codes


class PerceptionSchemaError(ValueError):
    """Raised when model output is malformed or contains prohibited semantics."""


# The six non-authoritative scene booleans. Models occasionally emit stringy
# values ("none", "null", "yes") instead of a JSON boolean; we coerce ONLY these
# known perception fields, and ONLY conservatively: anything not clearly truthy
# resolves to False (the more restrictive reading — perception never escalates).
_OBSERVATION_BOOL_FIELDS = (
    "person_present",
    "vehicle_present",
    "package_present",
    "entrance_activity",
    "prolonged_presence",
    "repeated_activity",
)
_TRUE_TOKENS = {"true", "yes", "y", "1", "present", "detected"}


def _coerce_observation_bools(obj: dict[str, Any]) -> None:
    """In-place, conservative bool coercion for known scene fields only."""
    for field in _OBSERVATION_BOOL_FIELDS:
        value = obj.get(field)
        if isinstance(value, str):
            obj[field] = value.strip().lower() in _TRUE_TOKENS
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            obj[field] = value != 0


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    # Tolerate a fenced or prefixed reply by taking the first balanced {...} block.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise PerceptionSchemaError("no JSON object found in model output")
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise PerceptionSchemaError(f"malformed JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise PerceptionSchemaError("model output is not a JSON object")
    return obj


def parse_observation(text: str) -> SecurityObservation:
    obj = _extract_json_object(text)

    # Reject authority semantics explicitly (belt-and-suspenders with extra=forbid).
    bad = _PROHIBITED_OBSERVATION_FIELDS & {str(k) for k in obj}
    if bad:
        raise PerceptionSchemaError(f"model emitted prohibited authority fields: {sorted(bad)}")

    if "observation_codes" in obj and isinstance(obj["observation_codes"], list):
        obj["observation_codes"] = filter_codes(obj["observation_codes"])

    # Perception-layer tolerance: coerce stringy scene booleans before validation.
    # Authority fields are already rejected above, so this cannot relax any decision.
    _coerce_observation_bools(obj)

    try:
        return SecurityObservation.model_validate(obj)
    except Exception as exc:  # noqa: BLE001 — any schema issue → safe rejection
        raise PerceptionSchemaError(f"schema validation failed: {exc}") from exc
