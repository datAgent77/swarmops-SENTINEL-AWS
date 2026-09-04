# IMPLEMENTATION_PLAN — Sentinel

Phased plan. Each phase ends **green** (pytest + ruff + web eslint/build) and
leaves the demo runnable. Reuse the deterministic governance/approval/audit core;
build the Ring → Bedrock → incident pipeline and the officer-shift UI on top.

## Guardrails for every phase

- Keep the invariant: **no LLM in the authorization path.** Bedrock feeds context
  (observations) and explanations only.
- Every new external integration is **key-gated** with a deterministic local
  fallback, so `make test` and the no-key demo never call AWS/Ring (mirror the
  existing `providers/{llm,comms,context,publish}` factories + `ResilientProvider`).
- Tests must pass with **no `.env`** present (CI has no keys). *(P00 note: the
  local `.env` holds live sponsor keys; running pytest with it in place fails
  key-absence assertions. Real suite is green with `.env` moved aside — 69/69.)*
- Deterministic seed: the 23:42 scenario reproduces byte-stable on reset.
- Honest integration status everywhere.
- Update `HACKATHON_CHANGES.md` and `FRICTION_LOG.md` as you go.

## Phases

### P01 — Incident domain + lifecycle (no external calls)
- Decide the persistence shape (recommended: **`security_incidents` table** +
  nullable `incident_id` on `events`/`approvals`/`governance_decisions`; new
  Alembic migration, existing schema untouched).
- Add the incident lifecycle transition table (mirror `state_machine.py`):
  `Detected → Assessed → Escalated → Approved/Denied → Actioned → Closed`.
- Domain enums + schemas for incidents.
- Unit tests for lifecycle transitions.
- **Exit:** new domain/migration tests green; no infra beyond Postgres touched.

### P02 — Governance extension + entrance context
- Extend `governance/engine.py` with deterministic entrance scenarios:
  `grant_temporary_access` → BLOCK unless (business hours ∧ verified visitor ∧
  approved request ∧ valid credential); `send_warning` → APPROVAL_REQUIRED
  (role `security`); `notify_security`/`log_incident` → ALLOW. Keep pure function.
- `services/context_service.py`: business hours, expected visitors, access
  requests, credentials → context dict.
- Tests: the winner-moment context yields the exact DENY reasons; a benign daytime
  context yields ALLOW.
- **Exit:** deterministic DENY / APPROVAL_REQUIRED proven by tests.

### P03 — Incident Engine + correlation + governed actions
- `services/incident_service.py` + `orchestration/incident_workflow.py`:
  correlate an event burst into one incident; drive the lifecycle; reuse
  `GovernanceDecisionRepository`, `ApprovalRepository`, `EventRepository`,
  `coordinator` (pause/resume), SSE.
- Governed Action Executor with an **idempotency guard** (new table) so
  `send_warning` fires exactly once.
- **Exit:** end-to-end incident test (fake events → DENY → warning →
  APPROVAL_REQUIRED → approve → exactly-once action → Closed), no network.

### P04 — Bedrock Perception (AWS Builder mini)
- `providers/llm/bedrock.py` (reasoning) + `perception/` (snapshot+meta →
  structured observation JSON: `person_present`, `package`, `prolonged_activity`,
  `confidence`). boto3 `bedrock-runtime`; behind the provider abstraction with a
  deterministic local fallback (`get_provider`-style).
- Feed observation into context; **never** into the decision. Low confidence →
  more restrictive branch.
- Config: AWS region/model/creds in `config.py`; key-gated; add to
  `active_sponsors()`-style status.
- **Exit:** perception tests pass with the local fallback; real Bedrock path
  behind a flag, smoke-tested manually.

### P05 — Ring Event Intake
- `ring/` module: OAuth 2.0, webhook receiver with **HMAC-SHA256 verification**,
  event normalization, snapshot retrieval, and a **simulator/replay source** for
  the 23:42 burst. Honest integration status.
- **Exit:** replayed Ring events flow intake → incident → decision; HMAC verify
  tested (accept valid, reject tampered).

### P06 — Sentinel console (officer shift UI)
- Reskin `apps/web`: incident timeline, live "on duty" status, winner-moment
  chain, approve/deny. Reuse `Timeline`, `ApprovalPanel`, `MetricsRail`, SSE
  client, `CompletionOverlay`.
- **Exit:** eslint + build green; demo page renders the full chain.

### P07 — Alexa+ MCP (human interface, cross-product)
- Self-hosted **Streamable HTTP** MCP server (spec 2025-11-25+):
  `list_open_incidents`, `get_incident`, `approve_action`, `deny_action`.
- Mutations route through `approval_service` (role re-checked; cannot bypass).
- **Exit:** MCP smoke test; "approve via Alexa+" path works end-to-end.

### P08 — Demo hardening + deploy
- Deterministic reset/seed; 3-minute shooting script; on-screen honesty caption.
- Confirm cloud story (default: keep Render/Vercel + Bedrock via boto3).
- Full green: pytest (with `.env` aside), ruff, web build.
- **Exit:** reproducible winner moment; submission checklist complete.

## Sequencing rationale

Incident domain + governance + context (P01–P03) are **pure and testable with no
external calls** — they lock the winner moment deterministically before any
AWS/Ring dependency exists. Perception (P04) and Ring (P05) then plug into a proven
pipeline. UI and Alexa+ (P06–P07) are presentation over a working core.

## Definition of done (submission)

- Winner moment reproducible on reset; DENY reasons rendered from the decision.
- Consequential actions: real approval + exactly-once, provable in the audit
  stream.
- Bedrock is the genuine brain (AWS Builder). MIT + in-window commits (Open
  Source). Public repo, <3-min video, product feedback + friction log filed.
