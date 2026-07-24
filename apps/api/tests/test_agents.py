"""Agent runner, structured-output validation/retry, and shared memory."""

import pytest

from app.agents.agent import AgentRunner
from app.agents.memory import MissionMemory
from app.agents.personas import PERSONAS
from app.agents.schemas import CEOOutput, StructuredOutputError, parse_structured
from app.providers.llm.base import LLMProvider, LLMRequest, LLMResponse, LLMUsage
from app.providers.llm.mock import MockProvider


async def test_agent_runner_produces_valid_structured_output() -> None:
    runner = AgentRunner(MockProvider())
    memory = MissionMemory(objective="Launch a secure portal")
    result = await runner.run(PERSONAS["ceo"], memory)
    assert isinstance(result.output, CEOOutput)
    assert 0.0 <= result.output_dict["confidence"] <= 1.0
    assert result.message  # a conversation line for the timeline
    assert result.reasoning_summary


class _Garbage(LLMProvider):
    """Always returns non-JSON — forces structured retry and mock fallback."""

    name = "garbage"
    model = "garbage"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text="this is not json", usage=LLMUsage(1, 1),
                           provider="garbage", model="garbage", latency_ms=1)


async def test_malformed_output_retries_then_falls_back_to_valid() -> None:
    runner = AgentRunner(_Garbage(), max_structured_retries=2)
    memory = MissionMemory(objective="x")
    result = await runner.run(PERSONAS["ceo"], memory)
    # After retries fail, the runner falls back to the deterministic mock → valid.
    assert result.output_dict.get("plan")
    assert result.response.provider == "mock"


def test_memory_accumulates_and_projects() -> None:
    memory = MissionMemory(objective="Launch a secure portal")
    memory.add_reasoning("ceo", "strategy set")
    memory.add_message("ceo", "I propose plan B")
    memory.add_risks(["prod exposure", "prod exposure", "data access"])
    memory.record_handoff("ceo", "pm")
    assert memory.known_risks == ["prod exposure", "data access"]  # deduped
    ctx = memory.prompt_context()
    assert "ceo" in ctx and "plan B" in ctx and "Launch a secure portal" in ctx


def test_parse_structured_rejects_invalid() -> None:
    with pytest.raises(StructuredOutputError):
        parse_structured("{not valid json", CEOOutput)
    with pytest.raises(StructuredOutputError):
        parse_structured('{"plan": "p"}', CEOOutput)  # missing required fields


async def test_memory_is_shared_across_agents() -> None:
    runner = AgentRunner(MockProvider())
    memory = MissionMemory(objective="Launch a secure portal")
    r1 = await runner.run(PERSONAS["ceo"], memory)
    # The orchestrator records each result into the shared memory (as _agent_step does),
    # and that memory is then passed to the next agent.
    memory.add_reasoning("ceo", r1.reasoning_summary)
    memory.add_message("ceo", r1.message)
    await runner.run(PERSONAS["pm"], memory)
    assert any(r["agent"] == "ceo" for r in memory.reasoning_log)
    assert "ceo" in memory.prompt_context()
