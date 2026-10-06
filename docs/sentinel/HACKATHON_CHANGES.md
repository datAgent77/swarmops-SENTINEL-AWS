# HACKATHON_CHANGES — Sentinel (Amazon Developer Hackathon)

> Honest disclosure of what is original hackathon work vs. reused. Required by the
> Official Rules.

## Summary

**Sentinel is original work built during the hackathon.** The repository contains
**no other product's code and no database** — every product component is new, and
the state is in-process by design.

The name **"SwarmOps"** in the product refers to Sentinel's own
deterministic-governance layer (`app/sentinel/governance`), not a separate project.

## Built during the hackathon (all new work)

- **Ring sensing** — `app/sentinel/ring/` (OAuth/HMAC-verified webhooks, Playground
  simulator, normalize, dedupe, media/live-view adapters, ingest) + `app/api/ring.py`.
- **Bedrock perception** — `app/sentinel/perception/` (boto3 Converse, strict-JSON
  observation, local Mock fallback) + `app/api/perception.py`. *(AWS Builder.)*
- **Deterministic authority** — `app/sentinel/governance/` (typed, versioned risk +
  policy engines) + `app/api/governance.py`.
- **Incident / officer / actions** — `app/sentinel/{models,enums,lifecycle,logic}.py`,
  `app/sentinel/officer/`, `app/sentinel/actions/` (role-scoped approvals, exactly-once
  execution engine) + `app/api/sentinel.py`.
- **Alexa+-compatible MCP server** — `app/mcp/` (Streamable HTTP, spec 2025-11-25).
- **Command screen** — `apps/web/app/sentinel/` (the `/sentinel` AI Security Officer UI).
- **Docs + tests** — `docs/sentinel/`, `docs/DEMO_SCRIPT_3MIN.md`,
  `docs/DEVPOST_SUBMISSION.md`, and the full `tests/test_sentinel_*` suite.

## Reused (generic framework utilities only — not product code)

- A small **error-envelope** helper (`app/domain/errors.py`, `app/api/errors.py`) and a
  **settings loader** (`app/config.py`) — standard FastAPI/pydantic glue, not specific to
  any product.
- Open-source libraries (FastAPI, pydantic, Next.js, boto3, …) under their own licenses,
  and AI coding assistants, as permitted by the Official Rules.

## What we do NOT claim

- We do not claim live Ring hardware actuation (locks/siren/audio) the partner API does
  not expose — physical access stays a governed, default-denied recommendation.
- We do not claim Bedrock decides anything — it perceives and explains; the deterministic
  policy decides.
- We do not bundle or depend on any prior product's application code.
