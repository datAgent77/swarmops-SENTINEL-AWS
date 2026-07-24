# Demo Flow

## Mission state machine

```
created → planning → assigned → running → waiting_approval → running → validating → completed
```

Off-happy-path terminals: `blocked`, `rejected`, `failed`. Invalid transitions are rejected by `app/orchestration/state_machine.py` (`assert_transition`).

## The demo workflow (`app/orchestration/workflow.py`)

Each agent step also emits live reasoning telemetry — `agent.thinking`, `agent.reasoning`
(with provider / model / token / cost), and `agent.message` (inter-agent conversation) — so a real
run streams ~40 events, not just the ~20 milestones below.

1. Mission is created (`POST /api/missions`), status `created`.
2. CEO Agent analyzes the objective → `planning`.
3. Product Manager Agent decomposes the mission.
4. Four mission tasks are created (developer, security, qa, finance).
5. Developer Agent starts implementation → `assigned` → `running`. A cost record is written.
6. Developer requests `production.deploy` (environment `production`).
7. Governance returns `approval_required` (risk 70). A `governance_decisions` row is written.
8. An `approvals` record is created (status `pending`).
9. Mission status → `waiting_approval`; developer → `waiting_approval`.
10. Execution **pauses** (the orchestrator awaits a real decision; the event loop is not blocked).
11. User approves or rejects via the API.
12. If approved → `running`; `deploy.succeeded` event is written.
13. An unauthorized agent (PM role) requests `customer_database.export`.
14. Governance **blocks** the action (risk 95). No data is exported.
15. The block is recorded (`governance.blocked` event) but the workflow continues.
16. QA Agent runs tests → `validating` → finds an issue.
17. Developer Agent resolves the issue → back to `running`.
18. QA Agent validates the fix (`qa.passed`) → `validating`.
19. Mission status → `completed`; all agents → `completed`.
20. Completion metrics are stored/derived and returned (events, blocked, approvals, tasks, cost/budget).

If the deploy is **rejected**, the mission stops safely at `rejected` and no deploy occurs.

## Evolution phase (runs automatically after `mission.completed`)

21. `evolution_service.evaluate_mission()` runs (wrapped so it can never fail the completed mission).
22. Each of the six agents is scored 0–100 from persisted mission data → a `performance_reports` row (`agent.evaluation.completed`).
23. Detected weaknesses become a data-only improvement proposal (`agent.improvement.proposed`).
24. A new immutable `agent_versions` row is created (`agent.version.created`). Low-risk → auto-approved and activated (`agent.version.activated`); high-risk → held as `pending_approval` for governance.
25. The dashboard's Mission Summary and Self-Evolving Workforce panel populate; a human can Approve/Reject any pending upgrade — the same governance gate as a production deploy.

## Rules
- The workflow never continues past the approval step until a real `POST /api/approvals/{id}/approve|reject` call is made. Approval is **never** simulated automatically.
- Governance outcomes are produced only by the deterministic engine and are never altered by the orchestrator.

## Governance scenarios (see `app/governance/engine.py`)

| # | Input | Result | Risk |
|---|---|---|---|
| A | Developer, `production.deploy`, production | `APPROVAL_REQUIRED` | 70 |
| B | Unauthorized role, `customer_database.export`, production | `BLOCK` | 95 |
| C | QA, `qa.run_tests` | `ALLOW` | 10 |
| D | Projected cost > agent budget or mission budget | `APPROVAL_REQUIRED` | 55 |
| E | Same agent fails a task 3× | Agent `quarantined` + `agent.quarantined` audit event; no automatic continuation | — |

## Timing
All pacing flows through `DEMO_EVENT_DELAY_MS` (default 650 ms). Set it lower (e.g. `150`) for a faster live demo, or `0` for instant (used by the test suite).
