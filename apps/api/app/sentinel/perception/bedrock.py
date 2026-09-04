"""Amazon Bedrock security-perception provider (AWS Builder integration).

Calls a Bedrock model via the ``bedrock-runtime`` Converse API and parses strict
JSON into a ``SecurityObservation``. Every failure (no boto3, no creds, timeout,
model error, malformed/authority output) degrades to a safe UNKNOWN result — it
never raises and never authorizes. Only the parsed observation + telemetry are
kept; the model's free text / reasoning is never stored.

No agent framework (Strands/AgentCore) is used: P00 established no genuine need,
and policy evaluation must never move into an agent runtime.
"""

from __future__ import annotations

import time
import uuid

from app.sentinel.perception.assemble import ok_result, unknown_result
from app.sentinel.perception.base import PerceptionInput, PerceptionResult
from app.sentinel.perception.parse import PerceptionSchemaError, parse_observation
from app.sentinel.perception.prompt import SYSTEM_PROMPT, build_user_prompt

# A cross-region inference profile id (e.g. "us.anthropic.claude-...") may be
# required depending on region; this default is overridable via BEDROCK_MODEL_ID.
DEFAULT_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
DEFAULT_REGION = "us-east-1"


class BedrockSecurityPerceptionProvider:
    name = "bedrock"

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_MODEL_ID,
        region: str = DEFAULT_REGION,
        timeout_s: float = 12.0,
        min_confidence: float = 0.5,
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._timeout_s = timeout_s
        self._min_confidence = min_confidence

    def _client(self):
        # Lazy import so the base install/tests never require boto3.
        import boto3  # type: ignore[import-untyped]
        from botocore.config import Config  # type: ignore[import-untyped]

        cfg = Config(
            read_timeout=self._timeout_s, connect_timeout=self._timeout_s,
            retries={"max_attempts": 1},
        )
        return boto3.client("bedrock-runtime", region_name=self._region, config=cfg)

    def _invoke(self, perception_input: PerceptionInput) -> str:
        content: list[dict] = [{"text": build_user_prompt(perception_input)}]
        if perception_input.image_bytes:
            fmt = perception_input.image_media_type.split("/")[-1]
            content.insert(0, {"image": {"format": fmt,
                                         "source": {"bytes": perception_input.image_bytes}}})
        response = self._client().converse(
            modelId=self._model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": content}],
            inferenceConfig={"maxTokens": 512, "temperature": 0.0},
        )
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        return "".join(b.get("text", "") for b in blocks)

    def perceive(self, perception_input: PerceptionInput) -> PerceptionResult:
        rid = uuid.uuid4().hex[:16]
        started = time.monotonic()
        try:
            text = self._invoke(perception_input)
        except Exception as exc:  # noqa: BLE001 — never raise; degrade to UNKNOWN
            latency = int((time.monotonic() - started) * 1000)
            reason = type(exc).__name__  # class name only — never the model's text
            return unknown_result(provider=self.name, model=self._model_id,
                                  request_id=rid, latency_ms=latency, reason=reason)

        latency = int((time.monotonic() - started) * 1000)
        try:
            observation = parse_observation(text)
        except PerceptionSchemaError as exc:
            return unknown_result(provider=self.name, model=self._model_id,
                                  request_id=rid, latency_ms=latency, reason=str(exc))
        return ok_result(observation, provider=self.name, model=self._model_id,
                         request_id=rid, latency_ms=latency, min_confidence=self._min_confidence)
