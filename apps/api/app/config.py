"""Application settings, loaded from environment with safe local defaults."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres is the source of truth. Sync psycopg driver (FastAPI runs sync
    # route handlers in a threadpool, so this does not block the event loop).
    database_url: str = Field(
        default="postgresql+psycopg://swarmops@127.0.0.1:5432/swarmops",
        alias="DATABASE_URL",
    )

    # Centralized demo pacing. Shorten before a live presentation via env.
    demo_event_delay_ms: int = Field(default=650, alias="DEMO_EVENT_DELAY_MS")

    # CORS is restricted to configured frontend origins. NoDecode disables
    # pydantic-settings' JSON parsing so a plain comma-separated env value works
    # (the validator below splits it); a JSON list is also accepted.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:3000"], alias="CORS_ORIGINS"
    )

    app_env: str = Field(default="development", alias="APP_ENV")

    # --- LLM / agents (Sprint 2) ------------------------------------------
    # "auto" picks the first provider whose API key is configured (Claude, then
    # OpenAI, then Gemini), otherwise the deterministic Mock provider. Force one
    # with "claude" | "openai" | "gemini" | "mock".
    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")
    llm_timeout_ms: int = Field(default=20000, alias="LLM_TIMEOUT_MS")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-3-5-sonnet-latest", alias="CLAUDE_MODEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # --- Sponsor integrations (all optional; each degrades to a local no-op /
    #     Mock fallback when its key is absent, so the demo never depends on one).
    # Pioneer (Fastino) — OpenAI-compatible model routing / adaptive inference.
    pioneer_api_key: str | None = Field(default=None, alias="PIONEER_KEY")
    pioneer_model: str = Field(default="gemma", alias="PIONEER_MODEL")
    pioneer_base_url: str = Field(default="https://api.pioneer.ai/v1", alias="PIONEER_BASE_URL")
    pioneer_adaptive: bool = Field(default=True, alias="PIONEER_ADAPTIVE")

    # Band — communication layer for AI agents (inter-agent messages mirrored to
    # a Band room via its REST Agent API).
    band_api_key: str | None = Field(default=None, alias="BAND_API_KEY")
    band_agent_id: str | None = Field(default=None, alias="BAND_AGENT_ID")
    band_base_url: str = Field(default="https://app.band.ai/api/v1", alias="BAND_BASE_URL")
    band_chat_id: str | None = Field(default=None, alias="BAND_CHAT_ID")

    # Senso — context layer for AI agents (ingest mission artifacts, retrieve
    # verified context). Base URL is configurable per the Senso API reference.
    senso_api_key: str | None = Field(default=None, alias="SENSO_API_KEY")
    senso_base_url: str = Field(default="https://api.senso.ai/v1", alias="SENSO_BASE_URL")

    # cited.md (Senso) — publish the mission report to the agentic web (real
    # action). Optional; without a key the report is generated and served locally.
    cited_api_key: str | None = Field(default=None, alias="CITED_API_KEY")
    cited_base_url: str = Field(default="https://cited.md/api", alias="CITED_BASE_URL")

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

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: object) -> object:
        # Managed Postgres providers (Render, Railway, Heroku) hand out a bare
        # "postgres://" / "postgresql://" URL. We use the psycopg (v3) driver, so
        # rewrite the scheme to "postgresql+psycopg://" unless a driver is set.
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("postgres://"):
                text = "postgresql://" + text[len("postgres://") :]
            if text.startswith("postgresql://"):
                text = "postgresql+psycopg://" + text[len("postgresql://") :]
            return text
        return value

    @property
    def demo_event_delay_seconds(self) -> float:
        return max(0.0, self.demo_event_delay_ms / 1000.0)

    def active_sponsors(self) -> list[str]:
        """Which sponsor integrations are configured (reflects real env keys —
        no secrets, just names). Drives the dashboard's "tools in use" indicator."""
        names: list[str] = []
        if self.pioneer_api_key or self.llm_provider == "pioneer":
            names.append("pioneer")
        if self.band_api_key:
            names.append("band")
        if self.senso_api_key:
            names.append("senso")
        if self.cited_api_key:
            names.append("cited")
        return names


@lru_cache
def get_settings() -> Settings:
    return Settings()
