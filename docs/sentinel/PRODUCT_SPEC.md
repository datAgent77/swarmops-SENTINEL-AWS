# PRODUCT_SPEC — Sentinel

## Product

**Sentinel — AI Security Officer for Ring.**

Sentinel is not a camera viewer, an AI chatbot, an alarm dashboard, or a generic
automation tool. **Sentinel behaves like a security officer**: it observes,
understands, assesses, decides within its authority, escalates when it must, acts
only on what it is permitted to do, and records everything.

## Product hierarchy

| Layer | Role | Backed by (in this repo) |
|-------|------|--------------------------|
| **Product** | Sentinel — AI Security Officer | this repository |
| **Sensing** | eyes & ears at the door | Ring Developer Platform *(new)* |
| **Intelligence** | understands the situation | Amazon Bedrock *(new provider)* |
| **Authority / Governance** | boundaries & risk | SwarmOps `app/governance/engine.py` *(extend)* |
| **Human interface** | approval when required | Alexa+ MCP *(new)* + web console |
| **Controlled actions** | what the officer may do | Governed Action Layer *(new)* |
| **Audit** | what actually happened | SwarmOps append-only `events` + SSE |

**Core principle:** Ring gives Sentinel eyes. Bedrock gives Sentinel
understanding. SwarmOps gives Sentinel boundaries. Humans retain authority over
consequential actions.

## User

- **Primary:** small-business owner / office manager / on-site security operator
  who has Ring at the entrance and wants intelligent monitoring **without handing
  an AI unrestricted control over the building.**
- **Secondary:** a small security team that receives escalations and grants
  approvals (the `security` role already exists in the governance model).

## Job to be done

> *"I want my entrance monitored intelligently, and I want an AI that can act like
> a security officer — but I need hard guarantees that it can never take a
> consequential action on its own."*

## Primary jobs (capabilities)

1. **Detect relevant entrance activity** — ingest Ring events (motion, doorbell).
2. **Distinguish routine from concerning activity** — correlate a burst of events
   into one incident; a delivery at noon ≠ repeated entry attempts at 02:00.
3. **Incorporate business context** — hours, expected visitors, access requests,
   credentials, known devices.
4. **Understand the scene** — Bedrock produces a *structured observation* from a
   snapshot + event metadata (person present, package, prolonged activity,
   confidence).
5. **Evaluate security risk** — deterministic situational risk + severity.
6. **Recommend an appropriate response** — the AI proposes; it never authorizes.
7. **Enforce security policy** — deterministic ALLOW / APPROVAL_REQUIRED / BLOCK
   (the engine's existing `DecisionResult`).
8. **Request approval** — route consequential actions to a human with the right
   role, via web console or Alexa+ (genuine pause/resume).
9. **Execute permitted actions exactly once** — notify, warn, escalate; never
   duplicate.
10. **Explain decisions** — plain language grounded in the actual decision.
11. **Preserve audit evidence** — every observation, decision, approval, and
    action is an immutable, seq-ordered event.

## Canonical workflow (the officer's shift)

```
OBSERVE → UNDERSTAND → ASSESS → DECIDE → ESCALATE → ACT → RECORD
```

Realized as the **incident lifecycle** (a state machine in the style of the
existing `app/orchestration/state_machine.py`):

```
Detected → Assessed → Escalated → Approved / Denied → Actioned → Closed
```

## Primary use case (the demo)

- **Location:** SaitALCorp office, front entrance.
- **Time:** 23:42 — building **CLOSED**.
- **Context:** expected visitor **NONE** · approved access request **NONE** ·
  credential **NONE**.
- **Ring events:** multiple human-motion events within minutes.
- **Sentinel builds one SecurityIncident** from the correlated events, attaches
  Bedrock's structured perception, evaluates deterministic risk and policy, and
  runs the winner-moment chain (see `WINNER_SPEC.md`).

## Actions Sentinel may take (Governed Action Layer)

| Action | Default decision | Rationale |
|--------|------------------|-----------|
| `log_incident` | ALLOW | Always safe; the record itself. |
| `notify_security` | ALLOW | Informational escalation. |
| `send_warning` | **APPROVAL_REQUIRED** (role: security) | Consequential; addresses a person. |
| `grant_temporary_access` | **BLOCK by default** | Physical consequence; only ever allowed with verified visitor + approved request + valid credential + business context. |

All actions pass through the deterministic engine; state-changing ones
(`send_warning`, `grant_temporary_access`, `notify_security`) are
idempotency-guarded so they fire **exactly once**.

## Explicit non-goals

- Not a real DLP / not production-grade computer vision.
- Not a replacement for a monitored alarm service or emergency dispatch.
- Does **not** actuate locks/sirens/audio unless a real, authorized integration
  exists; absent that, physical actions remain governed recommendations.
- No facial recognition / identity matching in the hackathon scope (privacy — see
  `ARCHITECTURE.md`).

## Success criteria

- The winner moment reproduces deterministically on reset.
- Every consequential action in the demo passes a real approval and runs exactly
  once, provable from the audit trail.
- AWS Builder mini satisfied: Bedrock is the genuine perception brain.
- Open Source mini satisfied: MIT, all Sentinel work committed in-window.
