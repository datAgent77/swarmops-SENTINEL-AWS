# SwarmOps — Hackathon submission

**Repo:** https://github.com/datAgent77/swarmops · **Demo video:** _<add 3-min link>_ · **Team:** _<names, ≤4>_

## Elevator pitch

A self-evolving AI workforce you can actually trust in production: six AI agents plan, build, review and
ship together, a **deterministic policy engine** governs every risky action (no LLM in the enforcement
path), and the workforce **measurably improves itself after every mission** — without ever being able to
touch its own code.

## Problem

Multi-agent systems are impressive until an agent does something irreversible — deploys to prod, exports
customer data, blows a budget — because the model *decided* to. And bolted-on "self-improvement" usually
means agents rewriting their own prompts/code with no audit trail, no human gate, no rollback. That's
ungovernable and unsafe.

## What it does

Runs a real mission ("Launch a secure customer support portal") through a CEO / PM / Developer / Security /
QA / Finance workforce. Agents reason with an LLM and hand off to each other, but every governed action
passes through a deterministic engine: production deploys **pause for a human**, unauthorized exports are
**blocked**, everything is an **append-only Postgres audit trail** streamed live to a React Flow "living
workforce" dashboard. After the mission, each agent is scored, an improvement is proposed and **versioned
under the same governance** (low-risk auto-activates; high-risk needs human approval; anything is
rollback-able).

## Why it's self-evolving — and why that's safe

Post-mission, an evolution layer scores each agent (10 metrics from persisted data), proposes **data-only**
config improvements, and writes them as **immutable versions**. Agents **cannot edit executable code** —
only configuration data rows; high-risk changes require the same human approval as a production deploy;
full history is preserved and reversible; and the whole step is wrapped so it can never break a completed
mission. Details: [`docs/architecture.md`](architecture.md), [`docs/domain-model.md`](domain-model.md).

## Sponsor tools used ("Tool use")

Each sits behind a provider interface, is key-gated, and degrades gracefully — a sponsor outage can never
break a mission. Full setup: [`docs/sponsors.md`](sponsors.md).

- **Pioneer** (Fastino) — OpenAI-compatible model routing / adaptive inference as a first-class LLM provider (`apps/api/app/providers/llm/pioneer.py`). Agents reason through it; the dashboard shows the routed model.
- **Band** — agent communication layer: inter-agent messages and governance events are mirrored to a Band room (`apps/api/app/providers/comms/`).
- **Senso** — context layer: agents retrieve verified context before reasoning and ingest their output back (`apps/api/app/providers/context/`).
- **Replay.io** — autonomous QA run against the SwarmOps dashboard (`apps/web`).

When configured, the dashboard header shows a **TOOLS** chip and the timeline logs a `sponsors.active`
event, so the integrations are visible in-product, not just in the sponsors' own tools.

## Tech stack

Next.js 16 + React 19 + React Flow (dashboard) · FastAPI + Python 3.11 · PostgreSQL 16 + SQLAlchemy +
Alembic · Server-Sent Events (durable, replayable) · deterministic governance engine · LLM provider
abstraction (Claude / OpenAI / Gemini / Pioneer / Mock).

## Run it

```bash
make install && make db-create && make demo   # → http://localhost:3000 → "Run demo mission"
```

Runs fully on a deterministic Mock with no keys. To use real models/sponsors, set keys in
`apps/api/.env` (see [`docs/sponsors.md`](sponsors.md)). Tests: `make test` (68 backend tests).

## How we map to the judging criteria

- **Idea** — governed autonomy + safe self-evolution is a real, unsolved production problem.
- **Technical implementation** — Postgres source of truth, deterministic governance, durable SSE, immutable versioning, 68 tests, clean build/lint.
- **Tool use** — Pioneer, Band, Senso integrated behind clean adapters; Replay QA on the app; visible in-product.
- **Presentation** — one-click demo, live graph, approval gate, completion overlay.
- **Autonomy** — agents act on live streamed data end-to-end; the only human touchpoint is the governance approval gate, by design.

## Notes

Built during the event on top of a pre-existing scaffold; the sponsor integrations, the living dashboard,
and the production hardening are the event work. A dated build snapshot can be produced with
`make snapshot` (see `scripts/snapshot.sh`).
