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

### [pending] [ring] — event intake & simulator
- To fill in P05: OAuth flow, webhook HMAC verification ergonomics, whether the
  Ring simulator can replay a deterministic motion burst, snapshot retrieval
  latency, docs clarity for partners without a physical device.

### [pending] [alexa-mcp] — Streamable HTTP MCP server
- To fill in P07: MCP spec (2025-11-25+) conformance, Alexa+ discovery/attachment
  of a self-hosted MCP, auth, tool schema ergonomics, approval round-trip UX.

## Product-feedback checklist (due at submission, per track/tool used)

- [ ] Ring — usability, effectiveness, onboarding, rebuild likelihood
- [ ] Bedrock — same four
- [ ] Alexa+ MCP — same four
- [ ] Any AWS Builder services used — same four
