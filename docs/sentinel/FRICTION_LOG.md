# FRICTION_LOG — Sentinel

> Running log of friction using Amazon tools/APIs/SDKs (Ring, Bedrock, Alexa+
> MCP) and the build itself. The hackathon awards a **10% judging bonus** for a
> friction log and requires product feedback (usability, effectiveness,
> onboarding, rebuild likelihood). Append dated entries — concrete and honest.

## Format

```
### [DATE] [AREA: ring | bedrock | alexa-mcp | aws | build] — short title
- Context: what we were trying to do
- Friction: what was confusing / broken / slow
- Workaround: what we did
- Feedback to Amazon: the specific ask
- Rebuild likelihood impact: +/- and why
```

## Entries

### 2026-09-04 [build] — P00 repository inspection (swarmops base)
- Context: Assessing the existing SwarmOps codebase for reuse under the Sentinel
  product framing on the new `swarmops-SENTINEL-AWS` repo.
- Friction: (1) The full test suite appears to fail when run with the developer's
  local `.env` present, because several tests assert key-absence behavior
  ("defaults to Mock without a key", "publishes locally without CITED_API_KEY")
  and pydantic-settings loads `.env` from disk regardless of process env. With
  `.env` moved aside the suite is **69/69 green**. (2) One pre-existing ruff nit:
  `alembic/env.py` import block unsorted (I001, auto-fixable). (3) macOS
  case-insensitive FS: a top-level `docs/ARCHITECTURE.md` would clobber the
  existing `docs/architecture.md`, so Sentinel docs live under `docs/sentinel/`.
- Workaround: Run pytest with `.env` temporarily moved aside for a true reading;
  keep Sentinel docs namespaced.
- Feedback to Amazon: N/A (pre-Amazon-tooling).
- Rebuild likelihood impact: n/a. The base is clean, layered, and green.

### [pending] [bedrock] — perception provider
- To fill in P04: model choice for snapshot→structured-observation, structured
  output reliability, latency, cost, region availability, boto3 auth setup,
  local-fallback parity.

### 2026-09-04 [ring] — P02 sensing layer against the Partner API docs
- Context: Building the real Ring sensing layer (provider abstraction, webhook
  intake, normalization, correlation) from the current official Ring Partner API
  documentation (developer.amazon.com/docs/ring), without a physical device or
  issued partner credentials.
- Friction (real, from documentation review):
  1. **Two doc surfaces.** Ring content is split between developer.amazon.com/docs/ring
     (the current Partner API) and developer.ring.com (Appstore). It's not obvious
     up front which is authoritative for a webhook/event integration.
  2. **Base host naming.** The Partner API base is `https://api.amazonvision.com`
     (not a `ring.com` host), while OAuth is `https://oauth.ring.com`. The
     `amazonvision.com` host is surprising and easy to miss.
  3. **Signature scheme not centralized.** The release-notes page references a
     "Webhook v1.1 Payload Structure" and "HMAC-SHA256 verification" but does not
     inline the header name or signing string; the concrete scheme
     (`X-Signature: sha256=<hex over raw body>`, constant-time compare) lives only
     in the full API doc. Had to cross-read pages to pin it down.
  4. **Credentials gate real events.** Live webhooks require partner onboarding
     (client_id/secret + a registered Webhook URL). For a hackathon without a
     device, the honest path is the simulator emitting the *documented* payload
     shape and signing it with the configured secret so it traverses the identical
     verify→normalize→correlate pipeline. The "physical device not required" claim
     holds only because of this.
  5. **Smart-detection categories.** PACKAGE/VEHICLE are modeled as
     `motion_detected` with `attributes.sub_type` rather than distinct event types;
     we normalized to that documented shape instead of inventing new types.
- Workaround: Grounded every field/endpoint in the API doc; simulator reproduces
  the documented envelope; developer provider verifies real signatures and only
  reports CONNECTED after a genuine signed event.
- Feedback to Amazon: consolidate the webhook signature spec (header + exact signed
  string) onto the release-notes/webhook page; clarify on the landing page which
  doc set is current for event integrations; make the `amazonvision.com` base host
  prominent in "Getting Started".
- Rebuild likelihood impact: neutral→positive once the base host and signature
  scheme are located; the payload shape is clean and easy to normalize.
- Still to verify with real access (P05+): OAuth account-linking UX, live snapshot
  retrieval latency, and whether Ring Playground offers a hosted event generator
  beyond the documented webhook shape.

### [pending] [alexa-mcp] — Streamable HTTP MCP server
- To fill in P07: MCP spec (2025-11-25+) conformance, Alexa+ discovery/attachment
  of a self-hosted MCP, auth, tool schema ergonomics, approval round-trip UX.

## Product-feedback checklist (due at submission, per track/tool used)

- [ ] Ring — usability, effectiveness, onboarding, rebuild likelihood
- [ ] Bedrock — same four
- [ ] Alexa+ MCP — same four
- [ ] Any AWS Builder services used — same four
