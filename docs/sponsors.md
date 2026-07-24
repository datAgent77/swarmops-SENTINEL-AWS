# Sponsor integrations

SwarmOps integrates hackathon sponsor tools through the same discipline as the rest of the codebase:
each vendor sits behind a small **provider interface**, business logic never imports a vendor SDK
directly, and every integration is **key-gated and resilient** — with no key it uses a local no-op or
the Mock provider, and if a vendor call fails it degrades silently so a sponsor outage can never break a
mission. This maps directly onto the **"Tool use"** judging criterion.

| Sponsor | What it is | Where it plugs into SwarmOps | Enable with |
|---|---|---|---|
| **Pioneer** (Fastino) | OpenAI-compatible model routing / adaptive inference | `app/providers/llm/pioneer.py` — a 4th LLM provider behind the existing `LLMProvider` interface | `PIONEER_KEY` (+ `LLM_PROVIDER=pioneer`) |
| **Band** | Communication layer for AI agents | `app/providers/comms/` — inter-agent messages + governance events mirrored to a Band room | `BAND_API_KEY` |
| **Senso** | Context layer for AI agents | `app/providers/context/` — agents retrieve/ingest verified context, fed into mission memory | `SENSO_API_KEY` |
| **cited.md** (Senso) | Publishing endpoint for the agentic web | `app/providers/publish/` — the finished mission report is published as a **real action** | `CITED_API_KEY` |
| **Replay.io** | Autonomous QA for web apps | The Next.js dashboard (`apps/web`) — run Replay QA against it | (external, see below) |

All of these are additive: **governance, the approval flow, the mission state machine, audit events, SSE, and
the database schema are untouched.** The Postgres audit trail remains the single source of truth; comms
and context are best-effort side channels that augment it.

---

## Pioneer — LLM provider (model routing / adaptive inference)

Pioneer is OpenAI-compatible, so it drops into the existing provider abstraction as a fourth option
alongside Claude / OpenAI / Gemini / Mock.

- **Code:** `app/providers/llm/pioneer.py` (`PioneerProvider`), wired into `app/providers/llm/factory.py` (`_AUTO_ORDER` + `_build`).
- **Enable:** get a key at `agent.pioneer.ai`, then in `apps/api/.env`:
  ```
  PIONEER_KEY=...
  LLM_PROVIDER=pioneer      # or leave "auto"; Pioneer is last in the auto order
  PIONEER_MODEL=gemma       # Pioneer routes/adapts from here
  ```
- **How it's used:** every agent's reasoning call goes through Pioneer's `/chat/completions` with
  `"adaptive": true`, and the `agent.reasoning` event records the model Pioneer actually routed to.
- **Verify:** run a mission and confirm the ENV chip / reasoning cards show `pioneer`. If Pioneer is down,
  the resilient wrapper falls back to Mock automatically.

## Band — agent communication layer

Band is the interaction layer for the "internet of agents": agents talk in **rooms**, and `@mentions`
route messages. SwarmOps mirrors its inter-agent conversation and the two governance moments (approval
gate, block) into a Band room via Band's REST Agent API (base `/api/v1`, header `X-API-Key`).

- **Code:** `app/providers/comms/` — `CommsProvider` interface, `BandComms` (REST), `LocalComms` (no-op),
  `factory.get_comms()`. Wired into `app/orchestration/workflow.py` (`ensure_room` at mission start,
  `send_message` after each `agent.message`, `post_event` on approval-required and block).
- **Enable (Band Hacker Guide flow):**
  1. Sign up at `app.band.ai`, go to **Agents → New Agent → External Agent**, name it (e.g. `SwarmOps`).
  2. Copy the **API Key** (shown once) and the **Agent UUID**.
  3. In `apps/api/.env`:
     ```
     BAND_API_KEY=band-...
     BAND_AGENT_ID=<agent-uuid>
     # optional: pre-create a room in the Band UI and pin it, otherwise one is created per mission
     # BAND_CHAT_ID=<room-id>
     ```
- **How it's used:** each agent message is posted as `[Agent] message`; governance decisions post as
  events. Watch the conversation appear live in the Band room during the demo.
- **Deeper option (time permitting):** register each of the six agents as its own Band External Agent and
  route hand-offs with real `@mentions` over Band's WebSocket runtime (`band-sdk` / `thenvoi`, open source
  at github.com/thenvoi). The REST mirror above is the low-risk version that needs no rearchitecture.
- **Field-name note:** Band's exact request-body fields aren't fully published; the ones used here
  (`content`, `mentions`, `title`, `type`) live in one place in `band.py` — align them with the live API
  reference if a call 4xxs (it will degrade gracefully until then).

## Senso — context layer

Senso ingests content and returns agent-ready, verified context. SwarmOps uses it as the shared context
layer across agents: before each agent reasons it **queries** Senso for relevant context (injected into
mission memory), and after it acts it **ingests** its output back so later agents can retrieve it.

- **Code:** `app/providers/context/` — `ContextProvider` interface, `SensoContext` (REST), `LocalContext`
  (no-op), `factory.get_context()`. Wired into `workflow._agent_step` (query before, ingest after) and
  surfaced in `MissionMemory.context_hint` → the agent prompt.
- **Enable:** get a key (Senso has a free tier), then:
  ```
  SENSO_API_KEY=...
  # SENSO_BASE_URL=https://api.senso.ai/v1   # adjust to match the Senso API reference
  ```
- **Verify:** with a key set, agent prompts include a "Verified context (Senso)" line. If Senso is
  unreachable, `query` returns empty and the mission proceeds on mission memory alone.
- **Endpoint note:** paths (`/content`, `/search`) and response shape are handled defensively in
  `senso.py`; confirm them against docs.senso.ai and adjust in that one file if needed.

## cited.md — publish the mission report to the agentic web (real action)

cited.md (by Senso) is *"an endpoint for the agentic web"* — a place agents publish verifiable, cited
content. SwarmOps closes the loop with it: when a mission finishes and self-evolution has scored the
run, SwarmOps builds a **mission report grounded entirely in the Postgres audit trail** (governance
decisions with the exact policy IDs they cite, the human-approval gate, cost/metrics, and the
self-evolution scores) and **publishes it** — a concrete external action the agents take, not just a
demo animation.

- **Code:** `app/publishing/report.py` (`build_mission_report` — Markdown grounded in persisted events,
  governance decisions, and evolution scores) + `app/providers/publish/` (`PublishProvider` interface,
  `CitedPublisher` REST, `LocalPublisher` no-op, `factory.get_publisher()`). Wired into
  `app/orchestration/workflow.py` after the evolution step, emitting a `mission.published` event.
- **Enable:** get a key at `cited.md`, then in `apps/api/.env`:
  ```
  CITED_API_KEY=...
  # CITED_BASE_URL=https://cited.md/api   # adjust to match the cited.md API reference
  ```
- **How it's used:** with no key the report is still generated and served at
  `GET /api/missions/{id}/report` (and the dashboard shows a **REPORT** chip); with a key it is
  **published to cited.md** and the dashboard shows a **PUBLISHED ↗** chip linking to the live URL. The
  report only ever restates what the audit trail already proves — every governance line cites its policy
  ID — so the published artifact is verifiable, matching cited.md's purpose.
- **Verify:** run a mission to completion; the timeline shows `mission.published` and
  `GET /api/missions/{id}/report` returns the grounded Markdown
  (`tests/test_sponsors.py::test_mission_report_is_grounded_and_published`).

## Replay.io — autonomous QA on our live, deployed dashboard

Replay QA is drop-in autonomous QA for web apps ("AI wrote the app, Replay QA finds what broke"). It
needs a public URL, so we **deployed the full SwarmOps stack** and pointed Replay QA at the live
dashboard — a genuine "we ran the tool on our own app" story, made stronger by the fact that our in-app
QA agent thematically mirrors it.

- **Live deployment:**
  - Frontend (Next.js) → **Vercel**: https://swarm-ops-self-evolwing-agents-hack.vercel.app
  - Backend (FastAPI) + Postgres → **Render** (one-click `render.yaml` blueprint), running on the
    deterministic **Mock** provider so the entire demo works with no API keys.
- **How we used it:** we added the Vercel URL as the target app in Replay QA and started an autonomous
  QA run. Replay explores the dashboard like a real user — launch a mission, approve the governance gate,
  watch it complete and self-evolve — and reports what breaks, with a recorded session behind each
  finding. The QA report is captured as demo evidence.
- **Thematic tie-in:** SwarmOps already runs an internal **QA agent** in every mission (finds an issue →
  Developer fixes it → QA re-validates), so "autonomous QA" is both a sponsor we use *and* a first-class
  part of the governed workflow.

---

## Demo narrative (ties Tool use + Autonomy)

> "Our agents reason through **Pioneer** (adaptive model routing), talk to each other over **Band**'s
> agent communication layer, and pull verified context from **Senso** — all under deterministic
> governance. When the mission finishes they take a real action: publishing an audit-grounded report to
> **cited.md**. And the dashboard itself is QA'd by **Replay**. Every sponsor sits behind a resilient
> adapter, so if one is down the mission still completes."

## Safety / resilience recap

- No key → local no-op (Band/Senso/cited.md) or Mock (Pioneer). The default `make demo` needs no sponsor
  keys; without `CITED_API_KEY` the report is still built and served locally, just not published.
- Any vendor error → swallowed; the mission always completes (proven by `tests/test_sponsors.py::test_mission_completes_when_sponsors_are_unreachable`).
- Governance/approval/state-machine/audit/SSE/DB unchanged.
