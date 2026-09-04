# WINNER_SPEC — Sentinel, AI Security Officer for Ring

> The single scene the whole submission is engineered to produce, deterministic
> and reproducible on demand. Everything in `PRODUCT_SPEC`, `ARCHITECTURE`, and
> `IMPLEMENTATION_PLAN` exists to make this moment real.

## One-sentence pitch

**Sentinel turns Ring from a camera that watches the door into an AI security
officer that understands what is happening, evaluates risk, follows policy, asks
for approval when necessary, takes permitted actions, and records exactly what
happened — autonomous, but never unaccountable.**

## Why this wins the Ring track

Ring track priorities are literally *access control, business systems, IoT
automation, accessibility, caretaking*. Sentinel is access control + business
security. Every other entrant shows **detection → alert**. Sentinel shows
**detection → understanding → deterministic authority → human approval →
exactly-once action → audit**. The differentiator is not the AI — it is the
**restraint**: an AI that recommends an action and is **denied by a rule it
cannot override**.

## The winner moment (demo climax)

Scene: **SaitALCorp office entrance, 23:42, building CLOSED.**

```
23:42  RING           motion_detected (front-entrance) ×3 within 6 min
       INTAKE         one SecurityIncident opened from correlated events
       BEDROCK        perception → { person_present: true, prolonged_activity: true,
                                     package: false, confidence: 0.91 }
       CONTEXT        building_open=false · expected_visitor=none ·
                      approved_access_request=none · valid_credential=none
       RISK (det.)    situational risk = HIGH   (deterministic, no LLM)

  AI  recommends:     GRANT TEMPORARY ACCESS
  SwarmOps:           DENIED
                      ├─ OUTSIDE_BUSINESS_HOURS
                      ├─ NO_VERIFIED_VISITOR
                      ├─ NO_APPROVED_ACCESS_REQUEST
                      └─ NO_VALID_CREDENTIAL

  AI  recommends:     SEND WARNING
  SwarmOps:           REQUIRE HUMAN APPROVAL   (role: security)
       HUMAN          approves  (web console or Alexa+)
       EXECUTOR       warning delivered — EXACTLY ONCE (idempotency-guarded)
       ESCALATION     security team notified
       AUDIT          full chain persisted to Postgres, append-only, seq-ordered
       INCIDENT       Detected → Assessed → Escalated → Approved → Actioned → Closed
```

## What judges must feel, in order

1. **"That's not a motion alert — it built a *case*."** (Correlation + business
   context, not one event.)
2. **"The AI wanted to open the door and the system said no."** (Deterministic
   DENY the model cannot override — the moat.)
3. **"A human stayed in the loop for the consequential action."** (Real approval,
   real role authority, genuine pause/resume.)
4. **"It did the action once, and I can see every step."** (Exactly-once +
   append-only audit stream.)

## Hard invariants this scene proves (already enforced in the base code)

- **Intelligence may be probabilistic. Authority must be deterministic.** Bedrock
  produces *observations*; `app/governance/engine.py` decides. The engine is a
  pure function — no I/O, no randomness, no time dependence (verified P00).
- **No LLM in the authorization path.** `AgentRunner` explicitly makes no
  governance decision; the orchestrator routes requested tools through
  `GovernanceEngine.evaluate` (verified P00, `app/agents/agent.py` +
  `app/orchestration/workflow.py`).
- **Consequential actions genuinely pause for a human.** The workflow awaits an
  asyncio event resumed only by a real approve/reject API call
  (`app/orchestration/coordinator.py`, `app/services/approval_service.py`);
  double-resolution returns `ConflictError` (idempotent).
- **Everything is auditable.** Append-only `events` table with a global `seq`,
  replayable over SSE with `Last-Event-ID` (`app/db/models.py::Event`,
  `app/api/stream.py`).

## Non-negotiables for the recording

- DENY reasons render **from the deterministic decision** (`policy_id` + reason),
  never narrated by the model.
- `Reset`/seed reproduces the identical 23:42 scenario (deterministic, like the
  existing seed).
- On-screen honesty caption: **"Ring events replayed from the simulator; every
  decision and action executes against the real backend."** (demo data ≠ faked
  execution.)

## Out of scope for the winner moment (do not fake)

- No real smart-lock actuation. `grant_temporary_access` is a **governed,
  default-denied** action that showcases the gate; if no lock is integrable it
  stays a denied recommendation, never a mimed unlock.
- No real two-way audio / siren — the Ring partner API does not expose these to
  developers (see `ARCHITECTURE.md` integration matrix).
