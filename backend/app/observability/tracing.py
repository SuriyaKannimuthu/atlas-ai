"""Tracing and logging configuration.

LangChain and LangGraph send traces to LangSmith automatically when `LANGSMITH_TRACING=true`
and `LANGSMITH_API_KEY` are set. We attach incident metadata and tags to every run so traces
can be filtered per incident, model, and environment.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def langsmith_enabled() -> bool:
    return os.getenv("LANGSMITH_TRACING", "").lower() == "true" and bool(
        os.getenv("LANGSMITH_API_KEY")
    )


def run_config(incident_id: str, settings: Settings, model_label: str) -> RunnableConfig:
    metadata: dict[str, Any] = {
        "incident_id": incident_id,
        "environment": settings.app_env,
        "model": model_label,
    }
    return RunnableConfig(
        configurable={"thread_id": incident_id},
        run_name="incident-investigation",
        tags=["atlas", settings.app_env],
        metadata=metadata,
        recursion_limit=60,
    )
