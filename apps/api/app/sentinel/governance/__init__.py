"""Sentinel authoritative decision layer (P04).

This is where Sentinel stops observing and starts governing. Two deterministic,
LLM-free engines:

- a **risk engine** that scores a scene from typed, configurable factors, and
- a **policy engine** that maps an action + risk + context to ALLOW /
  REQUIRE_APPROVAL / DENY.

No LLM participates in authoritative risk or policy. No eval/exec, no arbitrary
expressions, no model-written policy — only typed definitions in
``app.sentinel.governance.config``. Every decision carries the policy id, version,
and a content hash so the audit trail proves which policy produced it.
"""
