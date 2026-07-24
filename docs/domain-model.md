# Domain Model

All entities are persisted in PostgreSQL. **Primary keys are UUIDs. All timestamps are timezone-aware UTC.** Money is stored as `NUMERIC(10,2)`.

## Entities

| Table | Purpose | Key fields |
|---|---|---|
| `organizations` | Tenant container | `id`, `name`, `created_at` |
| `agents` | The workforce | `id`, `organization_id`, `key`, `name`, `role`, `team`, `status`, `allowed_tools` (JSONB), `budget_limit_usd`, `failure_count` |
| `policies` | Seeded governance policies (for display/audit) | `id`, `organization_id`, `policy_id`, `description`, `default_result`, `risk_score` |
| `missions` | A unit of work | `id`, `organization_id`, `objective`, `budget_usd`, `status`, `created_at`, `updated_at`, `completed_at` |
| `mission_tasks` | Decomposed work items | `id`, `mission_id`, `agent_id`, `title`, `status`, `attempts` |
| `events` | Append-only audit trail | `id`, `seq` (global identity), `mission_id`, `type`, `actor_id`, `message`, `payload` (JSONB), `created_at` |
| `governance_decisions` | Every decision the engine made | `id`, `mission_id`, `agent_id`, `tool`, `resource`, `environment`, `result`, `risk_score`, `reason`, `policy_id` |
| `approvals` | Human-in-the-loop gates | `id`, `mission_id`, `agent_id`, `tool`, `resource`, `reason`, `policy_id`, `risk_score`, `status`, `created_at`, `decided_at` |
| `cost_records` | Per-action cost tracking | `id`, `mission_id`, `agent_id`, `description`, `amount_usd` |
| `performance_reports` | Per-agent post-mission score | `id`, `mission_id`, `agent_id`, `agent_key`, `score` (NUMERIC 5,2), `metrics` (JSONB), `weaknesses` (JSONB), `created_at` |
| `agent_versions` | Immutable agent version history | `id`, `agent_id`, `agent_key`, `version` (e.g. `"1.1"`), `parent_version`, `status`, `risk_level`, `reason`, `improvements` (JSONB), `changes` (JSONB, **data-only, never executable code**), `performance_delta` (JSONB), `created_at`, `activated_at` |

## Enums

- **MissionStatus:** `created → planning → assigned → running → waiting_approval → running → validating → completed`; off-happy-path terminals: `blocked`, `rejected`, `failed`.
- **AgentStatus:** `idle`, `working`, `waiting_approval`, `blocked`, `completed`, `quarantined`.
- **TaskStatus:** `pending`, `in_progress`, `blocked`, `done`, `failed`.
- **DecisionResult:** `allow`, `block`, `approval_required`.
- **ApprovalStatus:** `pending`, `approved`, `rejected`.
- **VersionStatus:** `proposed` (high-risk, awaiting approval), `approved`, `rejected`, `active`, `superseded`. Content is immutable; only this flag moves.
- **RiskLevel:** `low` (auto-activates), `high` (requires governance approval — system prompt, tool permissions, allowed actions, budget, security).

## Ordering & streaming
`events.seq` is a global monotonic identity column. It provides a stable total order for replay and doubles as the SSE event id, enabling `Last-Event-ID` reconnection.

## Notes
- Enum columns are stored as `VARCHAR` via a small `EnumString` type decorator (round-trips to the Python enum; no native PG enum types to migrate).
- The seed creates one organization (`SwarmOps Demo Org`), six agents (`ceo`, `pm`, `developer`, `security`, `qa`, `finance`), and five policies. It is idempotent.
