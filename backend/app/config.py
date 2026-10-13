"""Application settings, loaded from environment variables (and `.env` in development)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Atlas AI"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # --- Persistence -------------------------------------------------------------------
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'atlas.db').as_posix()}"
    # memory: tests only. sqlite: durable local dev. postgres: shared deployments.
    checkpointer: Literal["memory", "sqlite", "postgres"] = "sqlite"
    checkpoint_url: str = f"{(BACKEND_ROOT / 'atlas_checkpoints.db').as_posix()}"
    redis_url: str | None = None

    # --- Security ----------------------------------------------------------------------
    # JSON object mapping API key -> {"subject": "...", "role": "viewer|operator|approver|admin"}
    api_keys: dict[str, dict[str, str]] = Field(default_factory=dict)
    # Comma-separated or JSON list.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    # When true, the person who submitted an incident cannot approve its actions.
    require_separation_of_duties: bool = False
    rate_limit_per_minute: int = 20

    # --- Model gateway -----------------------------------------------------------------
    # Empty provider = deterministic offline mode (no LLM calls); useful for dev and CI.
    model_provider: str | None = None
    model_name: str | None = None
    model_temperature: float | None = None
    model_timeout_s: float = 60.0
    model_max_retries: int = 2

    # --- Workflow budgets --------------------------------------------------------------
    max_investigation_rounds: int = 2
    max_tool_calls: int = 40
    max_workflow_seconds: float = 600.0
    tool_timeout_s: float = 10.0
    tool_max_retries: int = 3
    tool_backoff_base_s: float = 0.2
    sufficient_confidence: float = 0.7

    # thread: run investigations on a background worker pool. inline: run in the request
    # (deterministic; used by tests and the evaluation runner).
    executor: Literal["thread", "inline"] = "thread"
    worker_threads: int = 4

    # Fault injection for reliability tests, e.g.
    # "logs.search:transient:2,github.get_commit:permanent:1"
    fault_injection: str = ""

    data_dir: Path = BACKEND_ROOT / "data"

    @field_validator("api_keys", mode="before")
    @classmethod
    def _parse_api_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return json.loads(value) if value.strip() else {}
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            if value.strip().startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def llm_enabled(self) -> bool:
        return bool(self.model_provider and self.model_name)


@lru_cache
def get_settings() -> Settings:
    return Settings()
