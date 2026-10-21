# Sentinel — Devpost submission (paste-ready)

> Deadline: **Oct 23, 2026 @ 12:00pm** (your local time). Fill the Devpost form
> field-by-field from the blocks below. Repo is PUBLIC + MIT, so no collaborators
> need to be added.

---

## 0) Tracks to select
- **Primary track:** Ring
- **Mini challenge(s):** AWS Builder · Open Source

---

## 1) Project name
Sentinel — AI Security Officer for Ring

## 2) Tagline / elevator pitch (one line)
AI-powered security decisions. Human-controlled authority — an AI officer for Ring that understands the scene, enforces policy, and never opens the door on its own.

## 3) What it does (description)
Sentinel turns a Ring camera from a device that only *watches* into an AI security
officer. It ingests Ring-format events through the Ring Developer Platform pipeline
and Playground simulator, correlates a burst into one **incident**, uses **Amazon
Bedrock** to produce a structured **observation**, computes **deterministic risk**,
and runs every proposed action through a **deterministic policy**: ALLOW /
REQUIRE_APPROVAL / DENY.

When the AI recommends granting temporary access to a stranger at a closed door
after hours, **the policy denies it** — a rule the model cannot override. A safer
action (warn the officer) requires **human approval** (web console or an
Alexa+-compatible MCP client), then executes **exactly once**, on an append-only
audit trail.

**Core principle: intelligence may be probabilistic; authority must be
deterministic; no LLM may authorize its own action.**

## 4) How we built it
- **Sensing — Ring:** HMAC-SHA256 `X-Signature` webhooks, documented `{meta,data}`
  payloads, and the Ring **Playground simulator** for events without a device.
  Verify → normalize → dedupe → correlate.
- **Intelligence — Amazon Bedrock:** `bedrock-runtime` Converse (inference profile
  `global.anthropic.claude-haiku-4-5`) → strict-JSON `SecurityObservation`;
  authority-shaped output is rejected; failures degrade to a safe UNKNOWN.
- **Authority — SwarmOps (our governance layer):** typed, versioned risk + policy
  engines; no LLM, no `eval`. Role-scoped, expiring approvals; idempotency- and
  concurrency-guarded **exactly-once** execution.
- **Human interface — Alexa+-compatible MCP:** self-hosted MCP server (spec
  **2025-11-25**, Streamable HTTP), 8 narrow typed tools, all calling the same authority.
- **Frontend/Backend:** Next.js `/sentinel` command screen + FastAPI, in-process
  state (no database), ~134 tests.

## 5) Built with (tags)
ring, amazon-bedrock, aws, mcp, alexa-plus, python, fastapi, next.js, typescript, boto3

## 6) Repo URL (public, MIT)
https://github.com/datAgent77/swarmops-SENTINEL-AWS

## 7) Demo video URL
<PASTE YOUTUBE LINK HERE>  (Public, English, under 3 min — sentinel_demo_v2.mp4, 2:20)

---

## 8) Product feedback (required — be candid; friction logs earn up to +10%)

**Ring (primary track).** Used the Ring Partner/Developer API shape — HMAC-SHA256
`X-Signature: sha256=…` webhook verification, the `{meta,data:{type,id,attributes}}`
event payload, and the Playground simulator to drive motion/button events without a
physical device. What worked: the simulator made a device-free demo possible, and the
payload contract is clear once found. What needs work: the docs are split across two
surfaces and the base host is `amazonvision.com`; the webhook signature scheme lives
only in the full API doc and took digging to find (see our friction log). Would build
with it again: yes — once the signature + payload contract is in hand it's clean.

**Amazon Bedrock (AWS Builder mini).** Used `bedrock-runtime` Converse via boto3 as the
perception brain, with inference profile `global.anthropic.claude-haiku-4-5`. What
worked: the Converse API is simple and the structured-JSON prompting is reliable; fast
and cheap for scene perception. What needs work: model access is a multi-step gate —
an IAM permissions *policy* vs *boundary* confusion, plus a separate Anthropic
use-case approval, and newer model IDs (e.g. Haiku 5.5) weren't grantable on our
account while Haiku 4.5 was. Listing which inference profiles are actually invokable
for the account would save a lot of trial and error. Would build again: yes.

**Alexa+ / MCP.** Built a self-hosted MCP server to spec 2025-11-25 over Streamable
HTTP with 8 typed tools. What worked: the spec is clear and the single-POST `/mcp` +
notifications model is easy to implement. What needs work: more reference examples of
the Streamable HTTP transport (vs stdio) would help newcomers. Would build again: yes.

## 9) AWS Builder mini — which AWS services and how
**Amazon Bedrock Runtime (Converse API)** via boto3 is Sentinel's perception layer.
A Ring event + scene metadata is sent to Bedrock (inference profile
`global.anthropic.claude-haiku-4-5`); the model returns a strict-JSON
`SecurityObservation` (person/vehicle/package present, prolonged/repeated activity,
visibility, confidence). Any authority-shaped field is rejected, and any failure
degrades to a safe UNKNOWN. Bedrock feeds *observations into context* and *prose into
explanations* — it never makes the security decision. Integration lives in
`apps/api/app/sentinel/perception/bedrock.py`.

## 10) Open Source mini — required fields
- **Open-source project / contribution URL:** https://github.com/datAgent77/swarmops-SENTINEL-AWS
- **Repo URL:** https://github.com/datAgent77/swarmops-SENTINEL-AWS
- **GitHub username:** datAgent77
- **License:** MIT (LICENSE in repo root)
- **Short description (what / how / why):** Sentinel is a new, MIT-licensed open-source
  project built during the hackathon. It demonstrates a reusable pattern — a
  **deterministic authority layer above probabilistic AI**, so an LLM can perceive and
  recommend but never authorize an irreversible action. How: a pure, versioned policy
  engine evaluates every AI-proposed action (ALLOW/REQUIRE_APPROVAL/DENY) with
  role-scoped human approval and exactly-once execution. Why it matters: any agent that
  can touch the physical or financial world needs provable limits; this pattern makes
  AI action accountable and auditable.

## 11) If the project existed before the hackathon — what we built/changed
Sentinel was built during the hackathon window. All of the Ring sensing
(`app/sentinel/ring/`), Bedrock perception (`app/sentinel/perception/`), the entrance
risk/policy engine (`app/sentinel/governance/`), incident/officer/action engines, the
Alexa+-compatible MCP server (`app/mcp/`), the `/sentinel` command screen, and all
tests/docs are original work created for this hackathon. "SwarmOps" is the name of
Sentinel's deterministic-governance layer, not a separate product; the repo contains
no other product's code and no database. Full breakdown:
`docs/sentinel/HACKATHON_CHANGES.md`.

## 12) Optional (recommended — friction logs can earn up to +10%)
- **Friction log:** see `docs/sentinel/FRICTION_LOG.md`. Highlights:
  1) *Ring webhook signature discovery* — expected the HMAC scheme in the quickstart;
     it was only in the full API doc under a different host. Severity: medium.
     Workaround: implemented from the full-API-doc spec. Suggestion: surface the
     `X-Signature` scheme in the Ring quickstart.
  2) *Bedrock model access* — expected "enable model → invoke"; hit IAM
     policy-vs-boundary confusion and a separate Anthropic use-case approval, and a
     newer model ID wasn't grantable. Severity: medium. Workaround: attached
     AmazonBedrockFullAccess as a *policy* and switched to an invokable inference
     profile. Suggestion: a per-account "invokable models" list in the console.
- **Feature requests:** (1) Ring: a signed sample webhook payload generator in the
  Playground — *important*. (2) Bedrock: account-scoped invokable-model listing API —
  *important*.
