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
       RISK (det.)    situational risk = 87/100 CRITICAL   (deterministic, no LLM)

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
       AUDIT          full chain recorded, append-only, in-process
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

## Hard invariants this scene proves (enforced in code)

- **Intelligence may be probabilistic. Authority must be deterministic.** Bedrock
  produces *observations*; `app/sentinel/governance/policy.py` + `risk.py` decide.
  The engines are pure functions — no LLM, no `eval`, no randomness.
- **No LLM in the authorization path.** Perception output is rejected if it carries
  any authority field (`app/sentinel/perception/parse.py`); the decision is the
  deterministic policy engine's, and the AI recommendation is only an input.
- **Consequential actions require a human with the right role.** Role is resolved
  server-side; the proposer cannot self-approve; approvals expire
  (`app/sentinel/officer/service.py`).
- **Exactly-once execution.** The idempotency- and concurrency-guarded engine
  (`app/sentinel/actions/engine.py`) never runs a key twice.
- **Everything is auditable.** Append-only, in-process incident timeline with
  trace/idempotency/policy metadata (`app/sentinel/officer/service.py`).

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
