# SwarmOps Architecture v0.6

## Goal
A reliable, impressive hackathon demo of a self-evolving autonomous AI workforce operating under deterministic governance, without coupling the product to any one model or sponsor vendor.

## Core flow
Mission → Orchestrator (explicit state machine) → Agent reasons via an LLM provider → Agent action → **Deterministic governance evaluation** → persisted event / decision / approval / cost → SSE → Mission Control UI → (on completion) **Evolution: evaluate → propose → version → govern.**

## Principles
1. **Deterministic policies enforce; LLMs only reason/explain.** The governance engine is a pure function — no I/O, no randomness, no time dependence, no LLM. Agents use an LLM to plan and converse, but the enforcement path never does.
2. **The backend is the source of truth.** All state lives in PostgreSQL. The frontend renders it and can be refreshed at any time without losing progress.
3. **Every meaningful action becomes an append-only event.** Events are never updated or deleted in normal execution.
4. **Vendors are adapters, not core dependencies.** Every LLM call goes through one provider interface; business logic never imports a vendor SDK, and the demo runs fully on a deterministic Mock with no keys.
5. **Self-improvement is data-only and governed.** Agents evolve configuration data (never executable code); high-risk changes require the same human approval as any production action.
6. **The demo workflow is bounded, repeatable, and centrally paced** (`DEMO_EVENT_DELAY_MS`).

## Components

### Backend (`apps/api`)
- `app/config.py` — settings (env-driven): `DATABASE_URL`, `DEMO_EVENT_DELAY_MS`, `CORS_ORIGINS`, and the LLM provider settings (`LLM_PROVIDER`, per-vendor keys/models, timeout, retries).
- `app/db/` — SQLAlchemy `Base`, ORM models (source of truth), session management, `EnumString` type.
- `app/domain/` — shared `enums`, Pydantic API `schemas`, domain `errors`.
- `app/governance/engine.py` — the deterministic policy engine (Scenarios A–E). No LLM, no I/O.
- `app/providers/llm/` — the **only** place a vendor is called. `base` (interface), `claude`, `openai`, `gemini`, `mock`, `resilient` (retry + Mock fallback), `factory` (provider selection), `pricing`.
- `app/agents/` — agent personas, structured-output schemas, per-mission memory, and the agent runner (reason → structured decision, with retry + Mock fallback on malformed output).
- `app/evolution/` — `evaluator` (10-metric score from persisted data), `improvement` (weakness → data-only change), `versioning` (immutable versions + governed activation/rollback), `policy` (risk classification), `service` (post-mission orchestration).
- `app/repositories.py` — repository classes; the only code that issues DB queries.
- `app/services/` — `MissionService`, `ApprovalService` (business logic; route handlers stay thin).
- `app/orchestration/` — `state_machine` (allowed transitions), `workflow` (the persistent orchestrator; agents reason, act, and pass through governance), `coordinator` (in-process SSE fan-out + approval resume signaling).
- `app/api/` — thin routers (`missions`, `approvals`, `stream`, `evolution`) + the error envelope.
- `alembic/` — migrations (initial schema + evolution tables). `app/seed.py` — idempotent seed.

### Frontend (`apps/web`)
A real-time Mission Control dashboard (App Router client component, split into `components/` + `lib/`). It loads the seeded org/agents, creates and starts missions, streams events via `EventSource`, and renders: a **React Flow workforce graph** (live per-agent status, version, score, model, cost, active-agent highlight, animated handoffs); a tabbed feed (timeline / conversation / reasoning); an approval side panel; animated live metrics; a mission-completion overlay; and the Self-Evolving Workforce panel. It **restores state on refresh** from the backend and respects reduced-motion / high-contrast preferences.

## Concurrency & non-blocking design
- FastAPI **sync** route handlers run in a threadpool, so synchronous SQLAlchemy calls never block the event loop.
- The orchestrator runs as an `asyncio` background task. The approval step `await`s an `asyncio.Event` (via the coordinator) — the mission genuinely pauses without blocking the server, and resumes only when a real approval API call arrives.
- SSE reads durable events from Postgres; an in-process notifier only carries wake-up signals (bounded queues; the DB is the durable backstop).
- LLM calls are async (`httpx`) with a per-call timeout and bounded retries; on failure the `ResilientProvider` transparently serves the deterministic Mock, so a mission never stalls on a vendor.

## Deliberately deferred (out of scope for the demo)
Auth / billing / multi-tenant authorization; external sponsor adapters beyond the LLM interface; horizontal scale-out (no Kafka/Redis/Celery/LangGraph/CrewAI; single in-process API with SSE, not WebSockets); agent self-modification of executable code (evolution is intentionally data-only).
