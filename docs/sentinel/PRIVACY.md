# Privacy — Sentinel

**Principle: judge behavior, not identity.** Sentinel decides from *what is happening*
at an entrance (motion, presence, timing, business context), never from *who* a person is.

## What Sentinel does NOT do (confirmed)

None of these exist anywhere in the codebase (verified by review; no such code or
dependency is present):

- ❌ Stranger **facial recognition** / face matching
- ❌ **Demographic inference** (age, gender, race, …)
- ❌ **Gait** identification
- ❌ **Voiceprint** identification
- ❌ **Cross-camera identity tracking** / re-identification

The perception layer emits only behavioral, non-identifying signals:
`person_present`, `vehicle_present`, `package_present`, `entrance_activity`,
`prolonged_presence`, `repeated_activity`, `visibility`, `confidence` — enforced by the
strict `SecurityObservation` schema (`app/sentinel/models.py`), which also forbids any
authorization field.

## Data minimization

- Ring media is treated as sensitive. Sentinel persists the **structured observation**
  and a **SHA-256 hash of the raw event payload** (`raw_metadata_hash`) for audit — never
  raw video, and never a sensitive media URL (`app/sentinel/ring/normalize.py`).
- Media retrieval is optional and best-effort; on any failure the system continues on
  metadata alone (`app/sentinel/ring/media.py`).
- Secrets, tokens, and media URLs are never logged (`app/sentinel/ring/*`).

## Untrusted scene content

Any text visible in a scene (signs, OCR) is treated as **untrusted data**: the model may
describe it but can never act on it (`app/sentinel/perception/prompt.py`;
`test_prompt_injection_is_described_not_obeyed`).

## Human authority & auditability

Consequential actions require a human with the right role, and every observation,
decision, approval, and action is on an append-only audit trail — so a person can always
see and contest what happened.

## Out of scope (hackathon)

Entrance monitoring implies notice/consent obligations in real deployments (signage,
retention policy, access controls on the audit trail). These are called out here and in
`ARCHITECTURE.md`; enforcing them operationally is beyond the hackathon scope.
