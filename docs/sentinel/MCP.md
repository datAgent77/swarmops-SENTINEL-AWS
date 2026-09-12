# Sentinel MCP — Alexa+ interface (development & deployment)

Sentinel exposes a **remote Model Context Protocol server** (spec **2025-11-25**)
over **Streamable HTTP** so Alexa+ can act as a security-officer interface. Alexa+
is an interface, not the authority: every tool calls the deterministic
`OfficerService`. SwarmOps decides; the human approves; the model never overrides.

## Endpoint & transport

- Single endpoint: **`POST /mcp`** (JSON-RPC 2.0: `initialize`, `tools/list`,
  `tools/call`, `ping`).
- Responses are `application/json`. **`GET /mcp` returns `405`** — no server-
  initiated SSE stream is offered. This is compliant **Streamable HTTP**, *not* the
  deprecated HTTP+SSE transport.
- `initialize` returns a `Mcp-Session-Id` header and
  `protocolVersion: "2025-11-25"`.
- Notifications (`notifications/*`, no `id`) are acknowledged with `202`.

## Tools (narrow, typed)

Read-only (`readOnlyHint: true`): `get_security_incident`,
`get_incident_explanation`, `get_allowed_actions`, `get_action_status`,
`get_incident_timeline`.
Write: `propose_security_action`, `approve_security_action`,
`reject_security_action`.

Every tool's `inputSchema` sets `additionalProperties: false`, so a caller cannot
smuggle extra fields (a forged `role`, a `skip_approval` flag). There is **no**
shell, generic command, raw DB, or policy-mutation tool.

## Authority model (bypass-proof)

- The approver's role is **resolved server-side** from the actor id; no request may
  claim a role. Wrong role → tool error `WRONG_ROLE`.
- Separation of duties: the proposer cannot approve their own action
  (`SELF_APPROVAL_FORBIDDEN`).
- Approvals expire; an expired approval cannot be approved (`APPROVAL_EXPIRED`).
- A `REQUIRE_APPROVAL` action never executes on propose — only after a valid
  approval, and then **exactly once** (idempotency-guarded).

## Local development

```bash
make dev            # API on :8080 (or run uvicorn app.main:app)
# initialize
curl -s localhost:8080/mcp -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}'
# list tools
curl -s localhost:8080/mcp -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
# call a tool
curl -s localhost:8080/mcp -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_incident_explanation","arguments":{"incident_id":"inc-demo"}}}'
```

For a public dev URL (Alexa+ needs remote reachability): tunnel with `ngrok http
8080` or `cloudflared`, and register the resulting `https://…/mcp` URL. Never put
secrets in the URL.

## Deployment

- The MCP endpoint ships inside the same FastAPI app already deployed on **Render**
  (see `render.yaml`); the public base URL exposes `/mcp` directly — no separate
  service required.
- Put the server behind HTTPS (Render provides TLS).
- **Secrets:** none are hardcoded. Ring, Bedrock (AWS), and DB credentials come
  from environment variables / the platform secret store (`RING_*`, `BEDROCK_*`,
  `AWS_*`, `DATABASE_URL`). `.env` is gitignored.
- **Auth (production):** front the endpoint with a bearer token / OAuth resource
  server and map the authenticated principal to an actor id + role in the
  `ActorRegistry`. In the hackathon build the actor registry is seeded for the demo;
  wiring real auth is a follow-up and does not change the authority semantics.

## Why this is safe by construction

The MCP layer can only *name* actions and *carry* an actor id. The decision
(ALLOW / REQUIRE_APPROVAL / DENY) is the deterministic policy engine's, and the
approval is a role-checked human step. No MCP call — however phrased by Alexa+ —
can skip approval, self-approve, or override policy.
