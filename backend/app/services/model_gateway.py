"""Single entry point for LLM calls.

Centralises provider selection, structured output, timeouts, retries, and usage accounting.
When no provider is configured the gateway reports itself as disabled and agents use their
deterministic implementations - the whole platform runs offline that way.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.config import Settings

T = TypeVar("T", bound=BaseModel)
EventSink = Callable[[str, dict[str, Any]], None]


class ModelUnavailableError(Exception):
    """The model could not produce a valid structured result."""


class ModelGateway:
    def __init__(self, settings: Settings, model: Any | None = None) -> None:
        self.settings = settings
        self._model = model
        if self._model is None and settings.llm_enabled:
            from langchain.chat_models import init_chat_model

            kwargs: dict[str, Any] = {
                "timeout": settings.model_timeout_s,
                "max_retries": settings.model_max_retries,
            }
            if settings.model_temperature is not None:
                kwargs["temperature"] = settings.model_temperature
            self._model = init_chat_model(
                settings.model_name, model_provider=settings.model_provider, **kwargs
            )

    @property
    def enabled(self) -> bool:
        return self._model is not None

    @property
    def label(self) -> str:
        if not self.enabled:
            return "offline-heuristics"
        return f"{self.settings.model_provider}:{self.settings.model_name}"

    def structured(
        self,
        schema: type[T],
        *,
        system: str,
        prompt: str,
        name: str,
        emit: EventSink,
    ) -> T:
        if self._model is None:
            raise ModelUnavailableError("no model configured")

        runnable = self._model.with_structured_output(schema, include_raw=True)
        started = time.perf_counter()
        try:
            result = runnable.invoke(
                [SystemMessage(content=system), HumanMessage(content=prompt)],
                config={"run_name": name, "tags": ["atlas", name]},
            )
        except Exception as exc:
            emit(
                "model_failed",
                {
                    "call": name,
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                    "latency_ms": _ms(started),
                },
            )
            raise ModelUnavailableError(str(exc)) from exc

        raw = result.get("raw")
        usage = getattr(raw, "usage_metadata", None) or {}
        emit(
            "model_called",
            {
                "call": name,
                "model": self.label,
                "latency_ms": _ms(started),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
        )
        parsed = result.get("parsed")
        if parsed is None:
            error = result.get("parsing_error")
            emit("model_failed", {"call": name, "error": f"unparseable output: {error}"[:500]})
            raise ModelUnavailableError(f"structured output failed: {error}")
        return parsed


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
