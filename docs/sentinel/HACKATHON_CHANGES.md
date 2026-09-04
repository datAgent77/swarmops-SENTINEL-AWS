# HACKATHON_CHANGES — Sentinel (Amazon Developer Hackathon 2026)

> Honest disclosure of what is **pre-existing** vs **built during the Amazon
> hackathon window**. Required by the Official Rules. Do not misrepresent
> pre-existing SwarmOps features as new work.

## Provenance statement

Sentinel is built **on top of an existing SwarmOps codebase** — a governed,
auditable, self-evolving AI-workforce backend originally created for the
Self-Evolving Agents Hackathon (see git history; commits predate the Amazon
window). The **deterministic governance core, approval flow, audit stream, and
provider abstraction are reused, not re-created.** The Amazon submission is the
**Sentinel product**: a Ring-sensed, Bedrock-powered AI Security Officer, plus the
Ring/Bedrock/Alexa+ integrations and the incident model built during the Amazon
window. This document is the source of truth for that boundary.

## PRE-EXISTING SwarmOps (reused, NOT new work)

Verified present in the repo at P00 (predates the Amazon window):

- Deterministic **governance engine** (pure function; Scenarios A–E) —
  `app/governance/engine.py`.
- **Mission state machine** (explicit transitions) —
  `app/orchestration/state_machine.py`.
- **Human approval** (DB-transactional, idempotent-by-conflict) +
  **genuine pause/resume** — `app/services/approval_service.py`,
  `app/orchestration/coordinator.py`.
- **Append-only audit** with global `seq` + **SSE replay / Last-Event-ID** —
  `app/db/models.py::Event`, `app/api/stream.py`, `app/repositories.py`.
- **LLM provider abstraction** (`LLMProvider` ABC, factory, `ResilientProvider` +
  Mock fallback) — `app/providers/llm/`.
- **Sponsor provider seams** (comms/context/publish, key-gated, local fallback) —
  `app/providers/{comms,context,publish}/`.
- **Agent runner** that makes **no** governance decision — `app/agents/agent.py`.
- **6-agent mission workflow**, **self-evolution**, cost tracking —
  `app/orchestration/workflow.py`, `app/evolution/*`, `providers/llm/pricing.py`.
- PostgreSQL + SQLAlchemy 2.0 + Alembic; Next.js live dashboard (`apps/web`).
- Test suite (**69 tests, green with a clean environment**), ruff, eslint,
  Next build — all passing at P00.

## BUILT DURING the Amazon hackathon (new work)

Filled in per phase as it lands. Planned new work:

- **Sentinel product framing** — `docs/sentinel/WINNER_SPEC.md`,
  `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, this file,
  `FRICTION_LOG.md`. *(P00 — created.)*
- **Incident domain + lifecycle** — `security_incidents` tables + nullable
  `incident_id`; incident state machine; Alembic migration. *(P01)*
- **Governance extension** — deterministic entrance scenarios (grant/warn/notify)
  in `governance/engine.py`. *(P02)*
- **Context Engine** — `services/context_service.py`. *(P02)*
- **Incident Engine / correlation + Governed Action Executor** (exactly-once) —
  `services/incident_service.py`, `orchestration/incident_workflow.py`. *(P03)*
- **Amazon Bedrock perception** — `providers/llm/bedrock.py` + `perception/`.
  *(P04, AWS Builder mini)*
- **Ring integration** — OAuth, HMAC-verified webhooks, snapshot retrieval,
  simulator/replay. *(P05)*
- **Sentinel officer-shift console** — reskin of `apps/web`. *(P06)*
- **Alexa+ Streamable HTTP MCP server** — approve/deny/list incidents. *(P07)*
- **Deterministic 23:42 demo seed + shooting script + deploy**. *(P08)*

## Reused-but-modified (call out explicitly)

- `app/governance/engine.py` — pre-existing engine; the entrance scenarios are new
  work; the base scenarios and pure-function contract are not.
- `apps/web` components — pre-existing live dashboard; the Sentinel reskin/wiring
  is new work.
- `app/config.py` — pre-existing; Ring/Bedrock settings are new work.
- Alembic schema — pre-existing tables untouched; incident tables are a new
  migration.

## Mini-challenge claims

- **AWS Builder:** Amazon Bedrock is the perception brain (P04) — a genuine
  integration, documented with product feedback.
- **Open Source:** repository is public and MIT-licensed; all Sentinel commits fall
  inside the Amazon window; pre-existing SwarmOps commits are older and disclosed
  here.

## What we will NOT claim

- We will not present the SwarmOps governance engine as invented for this
  hackathon.
- We will not claim live Ring hardware actuation (locks/siren/audio) the partner
  API does not expose.
- We will not claim Bedrock decides anything — it perceives and explains.
