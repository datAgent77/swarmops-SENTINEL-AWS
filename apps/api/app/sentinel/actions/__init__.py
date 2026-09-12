"""Governed action execution (P06).

Sentinel acts like a security officer — notify, warn, escalate, note — WITHOUT
pretending Ring performs physical controls it does not expose. Actions run through
a ``SecurityActionProvider`` (its own delivery channel), never through Ring; and
GRANT_TEMPORARY_ACCESS stays policy-governed (DENY by default).

Every execution is idempotency-keyed and serialized so that repeated HTTP/MCP/
approval/frontend/network retries and concurrent approvals can never produce a
duplicate execution — the original execution remains the only one.
"""
