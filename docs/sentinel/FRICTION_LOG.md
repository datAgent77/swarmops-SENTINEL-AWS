# FRICTION_LOG — Sentinel

Genuine developer friction encountered while building Sentinel against Amazon's
tools/APIs (Ring, Bedrock, Alexa+ MCP) and the codebase. Nothing here is invented.
The hackathon awards a 10% bonus for a friction log and requires product feedback
(usability, effectiveness, onboarding, rebuild likelihood).

Each entry: **date · tool · task · steps · expected · actual · severity · workaround ·
suggested improvement · status**.

---

### 2026-09-04 · ring · Locate the webhook signature scheme
- **Task:** Verify Ring webhook authenticity for real event intake.
- **Steps:** Read developer.amazon.com/docs/ring: get-started → release-notes → API doc.
- **Expected:** Signature header + signed string documented on the webhook page.
- **Actual:** Release notes say "HMAC-SHA256 verification" but omit the header name and
  signed string; the concrete scheme (`X-Signature: sha256=<hex over raw body>`,
  constant-time compare) is only in the full API doc.
- **Severity:** Medium (blocks a correct implementation until found).
- **Workaround:** Cross-read pages; implemented in `ring/webhook.py`.
- **Suggested improvement:** Put the exact header + signed-string on the webhook page.
- **Status:** Resolved.

### 2026-09-04 · ring · Find the Partner API base host
- **Task:** Configure API + OAuth base URLs.
- **Steps:** Follow the Partner API integration docs.
- **Expected:** A `ring.com` API host.
- **Actual:** API base is `https://api.amazonvision.com` (OAuth is `oauth.ring.com`) — the
  `amazonvision.com` host is surprising and easy to miss.
- **Severity:** Low.
- **Workaround:** Pinned as `RING_API_BASE` default (`ring/developer.py`).
- **Suggested improvement:** Make the base host prominent in "Getting Started".
- **Status:** Resolved.

### 2026-09-04 · ring · Demo without a physical device / partner credentials
- **Task:** Show a real Ring event entering the backend with no device.
- **Steps:** Look for a hosted event generator; register a webhook.
- **Expected:** A one-click sandbox event.
- **Actual:** Live webhooks need partner onboarding (client_id/secret + registered URL).
- **Severity:** Medium.
- **Workaround:** A simulator that emits the **documented** payload shape and signs it with
  the configured secret, so it traverses the identical verify→normalize→correlate path
  (`ring/simulator.py`). "Physical device not required" holds because of this.
- **Suggested improvement:** A hosted Playground that POSTs sample signed events to a dev URL.
- **Status:** Resolved (simulator).

### 2026-09-05 · bedrock · Choose a working model id
- **Task:** Call a Claude model on Bedrock via `bedrock-runtime` Converse.
- **Steps:** Set a model id and region; invoke.
- **Expected:** A plain `anthropic.claude-…` id works in any region.
- **Actual:** Newer Claude models often require a **cross-region inference profile** id
  (e.g. `us.anthropic.claude-…`) depending on region; a bare id can be rejected.
- **Severity:** Medium (runtime-only; not hit in the keyless demo).
- **Workaround:** `BEDROCK_MODEL_ID` is configurable with a documented `us.*` caveat; a
  deterministic Mock perceiver runs when unset (`perception/bedrock.py`, `factory.py`).
- **Suggested improvement:** Clearer, region-aware guidance on when a profile id is required.
- **Status:** Open (verify against a live account in a follow-up).

### 2026-09-06 · alexa-mcp · Streamable HTTP vs legacy SSE
- **Task:** Expose an MCP server Alexa+ can attach to (spec 2025-11-25).
- **Steps:** Implement a single `POST /mcp` JSON-RPC endpoint.
- **Expected:** Obvious transport guidance.
- **Actual:** Distinguishing **Streamable HTTP** from the deprecated HTTP+SSE transport,
  and that a server MAY answer `GET /mcp` with **405** when it offers no SSE stream, plus
  the notification→202 rule, all require careful spec reading.
- **Severity:** Low.
- **Workaround:** Implemented directly (`app/mcp/server.py`) — POST JSON-RPC, GET→405,
  notifications→202, session id on initialize.
- **Suggested improvement:** A minimal reference "Streamable-HTTP-only" server example.
- **Status:** Resolved.

### 2026-09-04 · build · Test suite vs a populated local `.env`
- **Task:** Run the suite locally.
- **Steps:** `make test` with a developer `.env` holding sponsor keys.
- **Expected:** Green.
- **Actual:** ~10 mission tests assert key-absence behavior; pydantic-settings loads `.env`
  from disk regardless of process env, so present keys fail those assertions.
- **Severity:** Low (CI has no `.env`).
- **Workaround:** Run with `.env` moved aside; documented in the README.
- **Suggested improvement:** A test env-file override in conftest.
- **Status:** Resolved (documented).

## Product-feedback checklist (per tool used, for submission)
- [x] Ring — usability/effectiveness/onboarding captured above; rebuild likelihood: **high** once base host + signature are located.
- [x] Bedrock — captured above; rebuild likelihood: **high** (Converse + strict JSON is clean).
- [x] Alexa+ MCP — captured above; rebuild likelihood: **high**.
