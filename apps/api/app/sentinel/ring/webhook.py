"""Ring webhook signature verification (HMAC-SHA256, ``X-Signature: sha256=<hex>``).

Per the Ring Partner API docs: compute ``HMAC-SHA256(secret, raw_body)``, hex-encode,
prefix with ``sha256=``, and compare in constant time against the ``X-Signature``
header. We verify the RAW body bytes (never a re-serialized payload) and never log
the secret or the signature.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Signature"
_PREFIX = "sha256="


def sign_body(raw_body: bytes, secret: str) -> str:
    """Produce a Ring-style ``sha256=<hex>`` signature for ``raw_body``.

    Used by the simulator to emit authentically-signed demo events so the full
    verify → normalize pipeline is exercised end to end.
    """
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"{_PREFIX}{digest}"


def verify_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Constant-time verification of the ``X-Signature`` header. False if missing,
    malformed, or mismatched — never raises on bad input."""
    if not secret or not signature_header:
        return False
    header = signature_header.strip()
    if not header.startswith(_PREFIX):
        return False
    expected = sign_body(raw_body, secret)
    return hmac.compare_digest(expected, header)
