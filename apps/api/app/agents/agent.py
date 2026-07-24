"""Agent runner: persona + memory + provider → validated structured output.

The runner builds a prompt from the persona and shared memory, calls the LLM
provider, validates the structured output (retrying malformed responses, and
falling back to a guaranteed-valid Mock as a last resort so the demo never
crashes), and returns a concise reasoning summary + a conversation line. It does
NOT make governance decisions and does NOT emit events — the orchestrator owns
those and routes any tool requests through the deterministic governance engine.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from pydantic import BaseModel

from app.agents.memory import MissionMemory
from app.agents.personas import Persona
from app.agents.schemas import StructuredOutputError, parse_structured
from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse
from app.providers.llm.mock import MockProvider


@dataclass
class AgentResult:
    persona_key: str
    display_name: str
    output: BaseModel
    output_dict: dict[str, Any]
    response: LLMResponse
    reasoning_summary: str
    message: str
    tool_requests: list[str]


def _summaries(key: str, output: BaseModel) -> tuple[str, str]:
    """Concise reasoning summary + a first-person conversation line (no chain-of-thought)."""
    d = output.model_dump()
    if key == "ceo":
        conf = int(round(float(d.get("confidence", 0)) * 100))
        return f"Selected the lowest-risk strategy (confidence {conf}%).", d["reasoning"]
    if key == "pm":
        n = len(d["tasks"])
        return f"Decomposed the mission into {n} tasks with dependencies.", f"I decomposed the work into {n} tasks."
    if key == "developer":
        if d.get("toolRequests"):
            return d["implementation"], f"Implementation ready. I need {', '.join(d['toolRequests'])}."
        return d["implementation"], "I fixed the issue and it's ready for re-validation."
    if key == "security":
        v = len(d.get("violations", []))
        return d["securityReview"], f"Security review done — {v} policy concern(s) flagged."
    if key == "qa":
        if d["passed"]:
            return "All checks passed.", "Validation successful."
        issue = (d.get("issues") or ["an issue"])[0]
        return f"Found {len(d.get('issues', []))} issue(s), severity {d['severity']}.", f"I found an issue: {issue}."
    if key == "finance":
        return d["recommendation"], f"Budget {d['budgetStatus']}: {d['recommendation']}"
    return "Acknowledged.", "Acknowledged."


class AgentRunner:
    def __init__(self, provider: LLMProvider, max_structured_retries: int = 2) -> None:
        self.provider = provider
        self.max_structured_retries = max_structured_retries
        self._mock = MockProvider()  # guarantees a valid structured output as a last resort

    async def run(self, persona: Persona, memory: MissionMemory,
                  instruction: str = "", extra_context: dict[str, Any] | None = None) -> AgentResult:
        base_prompt = memory.prompt_context()
        if instruction:
            base_prompt += f"\n\nYour task now: {instruction}"
        context = {"objective": memory.objective, **(extra_context or {})}
        request = LLMRequest(
            system_prompt=persona.system_prompt, user_prompt=base_prompt,
            temperature=persona.temperature, max_tokens=persona.max_tokens,
            schema_name=persona.schema_name, context=context,
        )

        output: BaseModel | None = None
        response: LLMResponse | None = None
        for _ in range(self.max_structured_retries):
            response = await self.provider.complete(request)
            try:
                output = parse_structured(response.text, persona.output_model)
                break
            except StructuredOutputError as exc:
                request = replace(
                    request,
                    user_prompt=base_prompt + f"\n\nYour previous reply was invalid ({exc}). "
                    "Return ONLY a single valid JSON object matching the required fields.",
                )
        if output is None:
            # Last resort: deterministic Mock always returns valid structured output.
            response = await self._mock.complete(request)
            output = parse_structured(response.text, persona.output_model)

        assert response is not None
        reasoning, message = _summaries(persona.key, output)
        tool_requests = list(getattr(output, "toolRequests", []) or [])
        return AgentResult(
            persona_key=persona.key, display_name=persona.display_name, output=output,
            output_dict=output.model_dump(), response=response, reasoning_summary=reasoning,
            message=message, tool_requests=tool_requests,
        )
