"""Sentinel MCP server package (Alexa+ interface).

A remote Model Context Protocol server (spec 2025-11-25) over Streamable HTTP.
It exposes narrow, typed tools that all call the authoritative OfficerService — no
shell, no generic command execution, no raw DB access, no arbitrary policy change.
Alexa+ is a security-officer INTERFACE; SwarmOps remains the authority.
"""
