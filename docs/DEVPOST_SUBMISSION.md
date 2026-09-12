# Devpost submission — Sentinel

**Tracks:** Ring (primary) · AWS Builder (mini) · Open Source (mini)
**Repo:** https://github.com/datAgent77/swarmops-SENTINEL-AWS · **License:** MIT
**Demo video script:** [`docs/DEMO_SCRIPT_3MIN.md`](DEMO_SCRIPT_3MIN.md) · **Proof:** [`docs/sentinel/INTEGRATION_PROOF.md`](sentinel/INTEGRATION_PROOF.md)

## Inspiration
A Ring camera at a closed office at midnight can tell you *there was motion*. It can't tell
you *what to do about it* — or make sure a machine doesn't do something irreversible on its
own. We wanted Ring to behave like a real security officer: understand the scene, weigh
risk, follow policy, ask a human when it matters, act, and leave an audit trail.

## What it does
Sentinel is an **AI security officer for an entrance**. It ingests real Ring events,
correlates a burst into one **incident**, uses **Amazon Bedrock** to produce a structured
**observation**, computes **deterministic risk**, and runs every action through a
**deterministic policy**: `ALLOW` / `REQUIRE_APPROVAL` / `DENY`. When the AI recommends
granting temporary access to a stranger at a closed door, **SwarmOps denies it** — a rule
the model cannot override. A warning requires a **human approval** (web console or
**Alexa+** via MCP), then executes **exactly once**. Everything is on an append-only audit
trail. Core principle: **intelligence may be probabilistic; authority must be
deterministic; no LLM may authorize its own action.**

## How we built it
- **Sensing — Ring Partner API** (`api.amazonvision.com`): HMAC-SHA256 `X-Signature`
  webhooks, documented `{meta,data}` payloads, and the Ring **Playground simulator** for
  events without a device. Verify → normalize → dedupe (`meta.request_id`) → correlate.
- **Intelligence — Amazon Bedrock** (`bedrock-runtime` Converse): snapshot + metadata →
  strict-JSON `SecurityObservation`; authority-shaped output is rejected; failures degrade
  to a safe `UNKNOWN`.
- **Authority — SwarmOps**: typed, versioned risk + policy engines (`policy_hash`), no LLM,
  no `eval`. Role-scoped, expiring approvals; idempotency- and concurrency-guarded,
  exactly-once execution.
- **Human interface — Alexa+ MCP**: a remote MCP server (spec **2025-11-25**) over
  **Streamable HTTP**, eight narrow typed tools, all calling the same authority.
- **Frontend** — a `/sentinel` command screen (Next.js) with a guided demo driving real
  endpoints. Backend: FastAPI + PostgreSQL.

## Challenges
- Ring's docs are split across two surfaces and the base host is `amazonvision.com`; the
  webhook signature scheme (`X-Signature: sha256=…`) lives only in the full API doc
  (see [`FRICTION_LOG.md`](sentinel/FRICTION_LOG.md)).
- Keeping the AI strictly out of the authorization path while still using it for perception
  and explanation — solved by a schema that forbids authority fields and a policy engine
  that treats a recommendation as input, never a decision.
- Guaranteeing exactly-once under retries and concurrent approvals (idempotency keys + a
  serializing execution engine).

## Accomplishments
- A believable "AI security officer" where the **hero moment is restraint** — an AI told
  *no* by a deterministic rule, with a human in the loop.
- Real Ring intake, real Bedrock perception, a real MCP server — all keyless-demoable.
- **~200 tests** covering the invariants: no-LLM-authorization, deterministic DENY,
  exactly-once, role/expiry/self-approval, adversarial prompts, and failure-mode safety.

## What we learned
- Users don't want an autonomous door-opener; they want an accountable one. Framing the
  AI as *perception + recommendation* and the policy as *authority* makes the product
  trustworthy and the demo compelling.
- A deterministic authority layer above probabilistic AI is a reusable pattern for any
  agent that can touch the physical or financial world.

## What's next
- Bind the Ring developer provider to a live account; add real snapshot-to-Bedrock vision.
- Durable persistence for incidents/audit (currently in-process for the officer layer).
- Production auth on the MCP endpoint mapped to real operator roles; retention controls.

## Disclosure — before vs during the hackathon window
- **Pre-existing (before Aug 31):** the SwarmOps governance *core* — the deterministic
  engine pattern, human-approval flow, append-only audit, and provider abstraction — from
  an earlier project. The mission-workforce app at `/` is that substrate.
- **Built during the Amazon window (new work):** the entire **Sentinel product** — Ring
  sensing (`app/sentinel/ring/`), Bedrock perception (`app/sentinel/perception/`), the
  entrance risk/policy (`app/sentinel/governance/`), incident/officer/action engines
  (`app/sentinel/officer/`, `app/sentinel/actions/`), the Alexa+ MCP server (`app/mcp/`),
  the `/sentinel` command screen, and all Sentinel tests + docs. Full breakdown:
  [`docs/sentinel/HACKATHON_CHANGES.md`](sentinel/HACKATHON_CHANGES.md).

## Privacy
Judge behavior, not identity: no facial recognition, demographic inference, gait/voiceprint
ID, or cross-camera tracking. See [`docs/sentinel/PRIVACY.md`](sentinel/PRIVACY.md).
