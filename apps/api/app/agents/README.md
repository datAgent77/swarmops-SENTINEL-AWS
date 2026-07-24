# AI Agents (Sprint 2)

Turns the deterministic six-step workflow into six reasoning AI employees, **without
changing** the governance engine, approval flow, mission state machine, audit events,
SSE, or the database schema. All of that is reused; this layer is additive.

## Provider abstraction (`app/providers/llm/`)
Business logic never calls Gemini directly — it depends only on `LLMProvider` and
obtains an instance from `get_provider()`.

- `base.LLMProvider` — `async complete(LLMRequest) -> LLMResponse`. Responses always
  report token `usage`, `provider`, `model`, and `latency_ms`.
- `mock.MockProvider` — deterministic, persona-flavored structured JSON. Default when
  no key is set and the automatic fallback when any real provider fails.
- `claude.ClaudeProvider` — Anthropic Messages API (httpx); assistant prefill forces JSON.
- `openai.OpenAIProvider` — OpenAI Chat Completions (httpx), `response_format: json_object`.
- `gemini.GeminiProvider` — Google Generative Language REST (httpx), JSON response mode.
- `resilient.ResilientProvider` — timeout + retry + fallback to Mock. Wraps the primary.
- `factory.get_provider()` — explicit `LLM_PROVIDER` (claude|openai|gemini|mock) wins;
  `auto` picks the first provider whose key is set (Claude → OpenAI → Gemini), else Mock;
  always wrapped with the resilient fallback.
- `pricing.estimate_cost(model, usage)` — token → USD.

Config (env): `LLM_PROVIDER` (auto|mock|claude|openai|gemini), `ANTHROPIC_API_KEY` +
`CLAUDE_MODEL`, `OPENAI_API_KEY` + `OPENAI_MODEL`, `GEMINI_API_KEY` + `GEMINI_MODEL`,
`LLM_TIMEOUT_MS`, `LLM_MAX_RETRIES`. Set exactly one key to use a real model.

## Personas (`app/agents/personas.py`)
Six persistent personas — CEO, PM, Developer, Security, QA, Finance — each with a role,
goal, **system prompt** (which specifies the exact JSON contract), allowed tools,
communication style, temperature, and max tokens.

## Structured output (`app/agents/schemas.py`)
Pydantic models enforce the required shape per agent (CEO `{plan,reasoning,risks,
confidence,nextAgent}`, PM `{tasks,dependencies,estimatedDuration,confidence,nextAgent}`,
Developer `{implementation,risks,toolRequests,nextAgent}`, QA `{issues,severity,passed,
nextAgent}`, Security `{securityReview,violations,recommendedActions}`, Finance
`{estimatedCost,budgetStatus,recommendation}`). `parse_structured` rejects invalid JSON;
the runner retries and, as a last resort, uses the Mock to guarantee a valid result.

## Memory (`app/agents/memory.py`)
`MissionMemory` is a structured abstraction (not prompt concatenation): mission summary,
reasoning log, completed tasks, known risks, handoffs, conversation, and each agent's
last structured output. The orchestrator threads one memory object through every agent
and renders a compact projection into each prompt.

## Agent runner (`app/agents/agent.py`)
Builds the prompt from persona + memory, calls the provider, validates/retries the
structured output, and returns a concise **reasoning summary** and a **conversation
line** (no raw chain-of-thought). It makes no governance decisions.

## Orchestration (`app/orchestration/workflow.py`)
Each step runs its agent (`agent.thinking` → `agent.reasoning` → `agent.message`),
updates shared memory, and records token/cost telemetry. Tool requests
(`production.deploy`, `security.scan`, `qa.run_tests`, …) are routed through the
**unchanged** deterministic governance engine; the deploy still pauses for human
approval and the unauthorized `customer_database.export` is still blocked.

## Telemetry
Per LLM call: input/output tokens, provider, model, latency, and cost — stored in the
`agent.reasoning` event payload and as a `cost_records` row, surfaced in mission metrics
(`input_tokens`, `output_tokens`, `llm_calls`) and shown as the dashboard "LLM Tokens" tile.
