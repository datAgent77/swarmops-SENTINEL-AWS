"""Sentinel — AI Security Officer domain (Amazon Developer Hackathon 2026).

New work built on top of the pre-existing SwarmOps base (see
docs/sentinel/HACKATHON_CHANGES.md). This package holds the strongly-typed core
domain that lets Sentinel behave like a security officer — observe, understand,
assess, decide, escalate, act, record — rather than a camera alert system.

P01 scope: pure domain models, the incident lifecycle state machine, and
deterministic helpers (event correlation, risk, access preconditions). No Ring,
no Bedrock, no persistence, and no final policy live here.

Invariant preserved from the base: intelligence may be probabilistic, but
authority must be deterministic, and no AI perception may carry authorization.
"""
