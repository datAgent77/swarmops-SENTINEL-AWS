"""Remote MCP server over Streamable HTTP (MCP 2025-11-25).

Single endpoint ``POST /mcp`` speaking JSON-RPC 2.0 (initialize, tools/list,
tools/call, ping). Responses are ``application/json`` (no server-initiated
streaming needed); ``GET /mcp`` returns 405 since no SSE stream is offered — this
is compliant Streamable HTTP, not the legacy HTTP+SSE transport.

Every tool is narrow and typed with ``additionalProperties: false`` so a caller
cannot smuggle extra fields (e.g. a forged role or a "skip_approval" flag). All
tools delegate to the authoritative OfficerService.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.domain.errors import DomainError
from app.sentinel.officer.service import officer

PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "sentinel-mcp", "version": "1.0.0"}

router = APIRouter(tags=["mcp"])

_STR = {"type": "string"}


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str],
          read_only: bool, handler: Callable[[dict], dict]) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object", "properties": properties, "required": required,
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": read_only, "title": name},
        "_handler": handler,
    }


# --- tool handlers (all delegate to the authoritative officer service) --------

def _h_get_incident(a: dict) -> dict:
    return officer.get_incident(a["incident_id"])


def _h_explanation(a: dict) -> dict:
    return officer.explain(a["incident_id"])


def _h_allowed_actions(a: dict) -> dict:
    return {"incident_id": a["incident_id"], "actions": officer.allowed_actions(a["incident_id"])}


def _h_propose(a: dict) -> dict:
    return officer.propose(a["incident_id"], a["action_type"], a["actor_id"],
                           action_request_id=a.get("action_request_id"))


def _h_approve(a: dict) -> dict:
    return officer.approve(a["incident_id"], a["approval_id"], a["actor_id"])


def _h_reject(a: dict) -> dict:
    return officer.reject(a["incident_id"], a["approval_id"], a["actor_id"])


def _h_action_status(a: dict) -> dict:
    return officer.action_status(a["incident_id"], a["action_id"])


def _h_timeline(a: dict) -> dict:
    return {"incident_id": a["incident_id"], "timeline": officer.timeline(a["incident_id"])}


TOOLS: list[dict] = [
    _tool("get_security_incident", "Fetch an incident's authoritative state.",
          {"incident_id": _STR}, ["incident_id"], True, _h_get_incident),
    _tool("get_incident_explanation",
          "Explain the incident's risk from authoritative state (never invented).",
          {"incident_id": _STR}, ["incident_id"], True, _h_explanation),
    _tool("get_allowed_actions", "List actions and their deterministic policy decisions.",
          {"incident_id": _STR}, ["incident_id"], True, _h_allowed_actions),
    _tool("propose_security_action",
          "Propose an action; the deterministic policy decides ALLOW/REQUIRE_APPROVAL/DENY. "
          "Pass a stable action_request_id so retries never duplicate execution.",
          {"incident_id": _STR, "action_type": _STR, "actor_id": _STR, "action_request_id": _STR},
          ["incident_id", "action_type", "actor_id"], False, _h_propose),
    _tool("approve_security_action",
          "Approve a pending action; validated by actor role, status, and expiry.",
          {"incident_id": _STR, "approval_id": _STR, "actor_id": _STR},
          ["incident_id", "approval_id", "actor_id"], False, _h_approve),
    _tool("reject_security_action", "Reject a pending action (role-validated).",
          {"incident_id": _STR, "approval_id": _STR, "actor_id": _STR},
          ["incident_id", "approval_id", "actor_id"], False, _h_reject),
    _tool("get_action_status", "Status of a proposed action and its execution.",
          {"incident_id": _STR, "action_id": _STR}, ["incident_id", "action_id"], True,
          _h_action_status),
    _tool("get_incident_timeline", "Append-only audit timeline for an incident.",
          {"incident_id": _STR}, ["incident_id"], True, _h_timeline),
]
_BY_NAME = {t["name"]: t for t in TOOLS}


def _public_tool(t: dict) -> dict:
    return {k: v for k, v in t.items() if not k.startswith("_")}


def _err(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _ok(id_: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _validate_args(args: dict, schema: dict) -> str | None:
    props = schema["properties"]
    for key in args:
        if key not in props:
            return f"unexpected argument '{key}'"
    for key in schema["required"]:
        if key not in args:
            return f"missing required argument '{key}'"
    return None


def _call_tool(id_: Any, params: dict) -> dict:
    name = params.get("name")
    tool = _BY_NAME.get(name)
    if tool is None:
        return _err(id_, -32602, f"unknown tool '{name}'")
    args = params.get("arguments") or {}
    problem = _validate_args(args, tool["inputSchema"])
    if problem is not None:
        return _err(id_, -32602, problem)
    try:
        structured = tool["_handler"](args)
    except DomainError as exc:
        # Authority/validation failures are tool errors, not protocol errors.
        return _ok(id_, {
            "content": [{"type": "text", "text": f"{exc.code}: {exc.message}"}],
            "structuredContent": {"error": exc.code, "message": exc.message, "details": exc.details},
            "isError": True,
        })
    import json

    return _ok(id_, {
        "content": [{"type": "text", "text": json.dumps(structured)}],
        "structuredContent": structured,
        "isError": False,
    })


def _dispatch(message: dict) -> dict | None:
    method = message.get("method")
    id_ = message.get("id")
    # A notification (no id) gets no response body.
    if id_ is None and method and method.startswith("notifications/"):
        return None
    if method == "initialize":
        return _ok(id_, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": "Sentinel security-officer tools. SwarmOps is the authority.",
        })
    if method == "ping":
        return _ok(id_, {})
    if method == "tools/list":
        return _ok(id_, {"tools": [_public_tool(t) for t in TOOLS]})
    if method == "tools/call":
        return _call_tool(id_, message.get("params") or {})
    return _err(id_, -32601, f"method not found: {method}")


@router.post("/mcp")
async def mcp_endpoint(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(_err(None, -32700, "parse error"), status_code=400)

    # Streamable HTTP: a single JSON-RPC message (batching not required here).
    response = _dispatch(payload) if isinstance(payload, dict) else _err(None, -32600, "invalid request")
    if response is None:
        return Response(status_code=202)  # notification acknowledged, no body

    headers = {}
    if isinstance(payload, dict) and payload.get("method") == "initialize":
        headers["Mcp-Session-Id"] = uuid.uuid4().hex
    return JSONResponse(response, headers=headers)


@router.get("/mcp")
async def mcp_get() -> Response:
    # No server-initiated SSE stream is offered; 405 is compliant Streamable HTTP.
    return Response(status_code=405, headers={"Allow": "POST"})
