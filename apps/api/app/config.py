"""Application settings for Sentinel, loaded from the environment / .env.

Sentinel's authoritative state is in-process, so there is no database. Ring and
Bedrock are both optional: with no keys, Ring runs on the documented Playground
simulator and Bedrock perception falls back to a deterministic Mock.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")

    # CORS is restricted to configured frontend origins. NoDecode disables
    # pydantic-settings' JSON parsing so a plain comma-separated env value works
    # (the validator below splits it); a JSON list is also accepted.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:3000"], alias="CORS_ORIGINS"
    )

    # --- Ring sensing layer ------------------------------------------------
    # Provider: "auto" (developer if configured, else simulator) | "developer"
    # | "simulator" | "mock".
    ring_provider: str = Field(default="auto", alias="RING_PROVIDER")
    ring_client_id: str | None = Field(default=None, alias="RING_CLIENT_ID")
    ring_client_secret: str | None = Field(default=None, alias="RING_CLIENT_SECRET")
    ring_webhook_secret: str | None = Field(default=None, alias="RING_WEBHOOK_SECRET")
    ring_access_token: str | None = Field(default=None, alias="RING_ACCESS_TOKEN")
    ring_api_base: str = Field(default="https://api.amazonvision.com", alias="RING_API_BASE")

    # --- Bedrock perception layer (AWS Builder) ----------------------------
    # Provider: "auto" (Bedrock if configured, else deterministic Mock) | "bedrock"
    # | "mock". AWS credentials come from the standard boto3 chain (env/role).
    perception_provider: str = Field(default="auto", alias="PERCEPTION_PROVIDER")
    bedrock_region: str = Field(default="us-east-1", alias="BEDROCK_REGION")
    bedrock_model_id: str | None = Field(default=None, alias="BEDROCK_MODEL_ID")
    perception_timeout_ms: int = Field(default=12000, alias="PERCEPTION_TIMEOUT_MS")
    perception_min_confidence: float = Field(default=0.5, alias="PERCEPTION_MIN_CONFIDENCE")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):  # tolerate a JSON list too
                import json

                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
