# API Reference

Base URL: `http://localhost:8000`. All request/response bodies use **snake_case**. Times are ISO-8601 UTC.

## Conventions

Errors use a consistent envelope:

```json
{ "error": { "code": "MISSION_INVALID_STATE", "message": "…", "details": {} } }
```

Common codes: `VALIDATION_ERROR` (422), `NOT_FOUND` (404), `CONFLICT` (409), `INVALID_STATE` / `INVALID_STATE_TRANSITION` (409).

## Endpoints

### `GET /health`
Liveness. → `{ "status": "ok" }`

### `GET /api/dashboard`
Seeded organization, the six agents, and all missions (most recent first).

### `POST /api/missions`  → 201
Create and start a mission.
```json
{ "objective": "Launch a secure AI-powered customer support portal.", "budget_usd": 5 }
```
Returns the mission (`id`, `status: "created"`, …). Execution begins immediately as a background task.

### `GET /api/missions`
List missions.

### `GET /api/missions/{mission_id}`
Mission **snapshot**: `mission`, `agents` (with live status), `tasks`, `pending_approval` (or `null`), and `metrics` (`events`, `blocked`, `approvals`, `tasks_total`, `tasks_done`, `total_cost_usd`, `budget_usd`). 404 if unknown.

### `GET /api/missions/{mission_id}/events`
The full append-only audit trail, ordered by `seq`.

### `GET /api/missions/{mission_id}/stream`  (SSE)
`text/event-stream`. Replays existing events from Postgres in order, then streams new ones live. Each message carries `id: <seq>` (for `Last-Event-ID` reconnection) and a JSON `data:` payload (the event). Sends `: keep-alive` comments every 15 s and closes on a terminal event (`mission.completed` / `mission.rejected` / `mission.failed`).

### `POST /api/approvals/{approval_id}/approve`
Approve a pending approval. Writes an `approval.granted` event and resumes the paused mission. Returns the mission snapshot.

### `POST /api/approvals/{approval_id}/reject`
Reject a pending approval. Writes an `approval.rejected` event; the mission stops safely (`rejected`). Returns the mission snapshot.

Approval rules: only `pending` approvals can be resolved; resolving again returns **409 CONFLICT**; unknown ids return **404 NOT_FOUND**; the approval status change and its event are written in one transaction.

### `GET /api/missions/{mission_id}/summary`
Post-mission evolution summary: `top_performer`, `most_improved`, `highest_cost_agent`, `highest_risk_agent`, `biggest_opportunity`, and the per-agent `reports` (all derived from persisted `performance_reports`).

## Evolution endpoints

### `GET /api/evolution/agents`
Per-agent evolution cards: `agent_key`, `name`, `current_version`, `performance_score`, `improvement_score`, `trend`, and `pending_version` (a high-risk upgrade awaiting governance, or `null`).

### `GET /api/evolution/agents/{key}/versions`
Full immutable version history for one agent (never overwritten).

### `GET /api/evolution/versions/{version_id}/comparison`
Compare a version against its parent using the persisted `performance_delta`.

### `POST /api/evolution/versions/{version_id}/approve`
Approve a high-risk (PROPOSED) version and activate it (supersedes the prior active version). Re-resolving returns **409 CONFLICT**.

### `POST /api/evolution/versions/{version_id}/reject`
Reject a PROPOSED version; the active version is unchanged.

### `POST /api/evolution/agents/{key}/rollback/{version_id}`
Re-activate a prior *legitimate* version (ACTIVE / SUPERSEDED / APPROVED). A rejected or still-proposed version cannot be rolled back into.

## Event types (non-exhaustive)
**Workflow:** `mission.started`, `plan.created`, `tasks.created`, `budget.reviewed`, `cost.recorded`, `governance.decision`, `approval.requested`, `mission.paused`, `approval.granted`, `approval.rejected`, `deploy.succeeded`, `governance.blocked`, `qa.issue_found`, `issue.fixed`, `qa.passed`, `agent.quarantined`, `task.failed`, `mission.completed`, `mission.rejected`, `mission.failed`.

**Agent reasoning (Sprint 2):** `agent.thinking`, `agent.reasoning` (carries `provider`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`), `agent.message` (inter-agent conversation).

**Evolution (Sprint 4):** `agent.evaluation.completed`, `agent.improvement.proposed`, `agent.version.created`, `agent.version.approved`, `agent.version.activated`, `agent.version.pending_approval`, `agent.version.rejected`, `evolution.failed`.
