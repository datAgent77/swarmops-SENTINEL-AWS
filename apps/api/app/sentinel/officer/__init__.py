"""Sentinel officer service (P05) — the single authoritative interface.

Both surfaces — the Alexa+ MCP server and the web UI — call THIS service. Neither
is the authority: every propose/approve/reject runs through the deterministic
governance engine and role-checked approvals here. Alexa+ is an interface, not a
decision-maker.

State is in-process for the hackathon (durable persistence is a later phase); the
authority semantics (deterministic policy, role validation, expiry, exactly-once
execution, audit timeline) are the point and are enforced here.
"""
