"""P05 tests: Alexa+ MCP server over Streamable HTTP (MCP 2025-11-25)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.sentinel.officer.service import DEMO_INCIDENT_ID

EXPECTED_TOOLS = {
    "get_security_incident", "get_incident_explanation", "get_allowed_actions",
    "propose_security_action", "approve_security_action", "reject_security_action",
    "get_action_status", "get_incident_timeline",
}
READ_ONLY = {
    "get_security_incident", "get_incident_explanation", "get_allowed_actions",
    "get_action_status", "get_incident_timeline",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _rpc(client: TestClient, method: str, params: dict | None = None, id_: int = 1):
    return client.post("/mcp", json={"jsonrpc": "2.0", "id": id_, "method": method,
                                     "params": params or {}})


def _call(client: TestClient, name: str, arguments: dict, id_: int = 1) -> dict:
    return _rpc(client, "tools/call", {"name": name, "arguments": arguments}, id_).json()


# --- protocol -----------------------------------------------------------------

def test_initialize_declares_streamable_http_protocol(client):
    res = _rpc(client, "initialize")
    assert res.status_code == 200
    body = res.json()["result"]
    assert body["protocolVersion"] == "2025-11-25"
    assert "tools" in body["capabilities"]
    assert body["serverInfo"]["name"] == "sentinel-mcp"
    assert res.headers.get("Mcp-Session-Id")


def test_notification_returns_202_no_body(client):
    res = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert res.status_code == 202


def test_get_is_405_not_legacy_sse(client):
    assert client.get("/mcp").status_code == 405


def test_tools_list_and_schemas(client):
    tools = _rpc(client, "tools/list").json()["result"]["tools"]
    assert {t["name"] for t in tools} == EXPECTED_TOOLS
    for t in tools:
        schema = t["inputSchema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False   # no smuggled fields
        assert t["annotations"]["readOnlyHint"] is (t["name"] in READ_ONLY)


def test_unknown_tool_is_protocol_error(client):
    body = _call(client, "delete_everything", {})
    assert body["error"]["code"] == -32602


def test_no_shell_or_db_tools_exposed(client):
    names = {t["name"] for t in _rpc(client, "tools/list").json()["result"]["tools"]}
    for forbidden in ("shell", "exec", "query", "sql", "command", "policy_change"):
        assert not any(forbidden in n for n in names)


# --- read tools ---------------------------------------------------------------

def test_incident_lookup(client):
    body = _call(client, "get_security_incident", {"incident_id": DEMO_INCIDENT_ID})
    result = body["result"]["structuredContent"]
    assert result["risk"]["risk_level"] == "CRITICAL"
    assert body["result"]["isError"] is False


def test_explanation_from_state(client):
    result = _call(client, "get_incident_explanation",
                   {"incident_id": DEMO_INCIDENT_ID})["result"]["structuredContent"]
    joined = " ".join(result["reasons"]).lower()
    assert "building is closed" in joined
    assert "no access request exists" in joined


def test_allowed_actions_tool(client):
    result = _call(client, "get_allowed_actions",
                   {"incident_id": DEMO_INCIDENT_ID})["result"]["structuredContent"]
    by = {a["action_type"]: a["decision"] for a in result["actions"]}
    assert by["GRANT_TEMPORARY_ACCESS"] == "DENY"
    assert by["SEND_WARNING"] == "REQUIRE_APPROVAL"


# --- approval flow via MCP ----------------------------------------------------

def test_propose_approve_flow(client):
    proposed = _call(client, "propose_security_action",
                     {"incident_id": DEMO_INCIDENT_ID, "action_type": "SEND_WARNING",
                      "actor_id": "owner-alex"})["result"]["structuredContent"]
    assert proposed["decision"] == "REQUIRE_APPROVAL"
    approval_id = proposed["approval_id"]

    approved = _call(client, "approve_security_action",
                     {"incident_id": DEMO_INCIDENT_ID, "approval_id": approval_id,
                      "actor_id": "officer-sam"})["result"]
    assert approved["isError"] is False
    assert approved["structuredContent"]["executed"] is True


def test_wrong_role_is_tool_error(client):
    proposed = _call(client, "propose_security_action",
                     {"incident_id": DEMO_INCIDENT_ID, "action_type": "SEND_WARNING",
                      "actor_id": "owner-alex"})["result"]["structuredContent"]
    denied = _call(client, "approve_security_action",
                   {"incident_id": DEMO_INCIDENT_ID, "approval_id": proposed["approval_id"],
                    "actor_id": "guest-01"})["result"]
    assert denied["isError"] is True
    assert denied["structuredContent"]["error"] == "WRONG_ROLE"


def test_reject_via_mcp(client):
    proposed = _call(client, "propose_security_action",
                     {"incident_id": DEMO_INCIDENT_ID, "action_type": "NOTIFY_SECURITY",
                      "actor_id": "owner-alex"})["result"]["structuredContent"]
    rejected = _call(client, "reject_security_action",
                     {"incident_id": DEMO_INCIDENT_ID, "approval_id": proposed["approval_id"],
                      "actor_id": "officer-sam"})["result"]["structuredContent"]
    assert rejected["status"] == "REJECTED"


# --- bypass attempts ----------------------------------------------------------

def test_extra_argument_is_rejected(client):
    # "Skip approval" / forged role cannot be smuggled: extra fields are refused.
    body = _call(client, "approve_security_action",
                 {"incident_id": DEMO_INCIDENT_ID, "approval_id": "x", "actor_id": "guest-01",
                  "role": "admin", "skip_approval": True})
    assert body["error"]["code"] == -32602
    assert "unexpected argument" in body["error"]["message"]
