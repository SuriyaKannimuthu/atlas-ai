"""Tool registry: the single choke point through which agents reach external systems.

Every invocation is checked against the caller's allowlist, validated against a Pydantic
schema, bounded by a timeout and a per-workflow call budget, retried with exponential backoff on
transient failures, and reported to an event sink for the audit trail.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.security.redaction import redact
from app.security.tool_access import is_tool_allowed

EventSink = Callable[[str, dict[str, Any]], None]


class ToolInvocationError(Exception):
    """Base class for tool failures surfaced to agents."""


class ToolNotPermittedError(ToolInvocationError):
    pass


class ToolValidationError(ToolInvocationError):
    pass


class TransientToolError(ToolInvocationError):
    """Retryable: timeouts, throttling, temporary unavailability."""


class PermanentToolError(ToolInvocationError):
    """Not retryable: bad request, missing resource, misconfiguration."""


class ToolBudgetExceededError(ToolInvocationError):
    pass


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    func: Callable[[Any], Any]
    side_effect: bool = False


@dataclass
class CallBudget:
    limit: int
    used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def consume(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                raise ToolBudgetExceededError(f"tool call budget of {self.limit} exhausted")
            self.used += 1


class FaultInjector:
    """Deterministic failure injection: "tool:kind:count" entries, comma separated.

    kind is one of transient, permanent, timeout. Each entry fails the next `count` calls.
    """

    def __init__(self, spec: str = "") -> None:
        self._lock = threading.Lock()
        self._remaining: dict[str, tuple[str, int]] = {}
        for entry in filter(None, (part.strip() for part in spec.split(","))):
            name, kind, count = entry.rsplit(":", 2)
            self._remaining[name] = (kind, int(count))

    def maybe_fail(self, tool_name: str, timeout_s: float) -> None:
        with self._lock:
            kind, count = self._remaining.get(tool_name, ("", 0))
            if count <= 0:
                return
            self._remaining[tool_name] = (kind, count - 1)
        if kind == "transient":
            raise TransientToolError(f"injected transient failure in {tool_name}")
        if kind == "permanent":
            raise PermanentToolError(f"injected permanent failure in {tool_name}")
        if kind == "timeout":
            time.sleep(timeout_s + 0.2)


_EXECUTOR = ThreadPoolExecutor(max_workers=16, thread_name_prefix="atlas-tool")


class ToolRegistry:
    def __init__(
        self,
        specs: list[ToolSpec],
        *,
        timeout_s: float = 10.0,
        max_retries: int = 3,
        backoff_base_s: float = 0.2,
        faults: FaultInjector | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._specs = {spec.name: spec for spec in specs}
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.faults = faults or FaultInjector()
        self._sleep = sleep

    def get(self, name: str) -> ToolSpec:
        return self._specs[name]

    def invoke(
        self,
        caller: str,
        name: str,
        args: dict[str, Any],
        *,
        emit: EventSink | None = None,
        budget: CallBudget | None = None,
    ) -> Any:
        emit = emit or (lambda _type, _payload: None)

        if name not in self._specs:
            raise ToolNotPermittedError(f"unknown tool {name!r}")
        if not is_tool_allowed(caller, name):
            emit("tool_denied", {"caller": caller, "tool": name})
            raise ToolNotPermittedError(f"{caller!r} is not permitted to call {name!r}")

        spec = self._specs[name]
        try:
            validated = spec.input_model.model_validate(args)
        except ValidationError as exc:
            emit("tool_failed", {"caller": caller, "tool": name, "error": "invalid arguments"})
            raise ToolValidationError(f"invalid arguments for {name}: {exc}") from exc

        attempt = 0
        while True:
            attempt += 1
            if budget:
                budget.consume()
            started = time.perf_counter()
            try:
                result = self._run_with_timeout(spec, validated)
            except TransientToolError as exc:
                elapsed = _ms(started)
                if attempt > self.max_retries:
                    emit(
                        "tool_failed",
                        {
                            "caller": caller,
                            "tool": name,
                            "attempt": attempt,
                            "error": str(exc),
                            "duration_ms": elapsed,
                            "retryable": True,
                        },
                    )
                    raise
                delay = self.backoff_base_s * (2 ** (attempt - 1)) * (0.5 + random.random() / 2)
                emit(
                    "tool_retry",
                    {
                        "caller": caller,
                        "tool": name,
                        "attempt": attempt,
                        "error": str(exc),
                        "backoff_s": round(delay, 3),
                    },
                )
                self._sleep(delay)
                continue
            except PermanentToolError as exc:
                emit(
                    "tool_failed",
                    {
                        "caller": caller,
                        "tool": name,
                        "attempt": attempt,
                        "error": str(exc),
                        "duration_ms": _ms(started),
                        "retryable": False,
                    },
                )
                raise
            emit(
                "tool_called",
                {
                    "caller": caller,
                    "tool": name,
                    "attempt": attempt,
                    "args": redact(validated.model_dump(mode="json")),
                    "duration_ms": _ms(started),
                    "side_effect": spec.side_effect,
                    "result_size": len(result) if isinstance(result, (list, dict)) else None,
                },
            )
            return result

    def _run_with_timeout(self, spec: ToolSpec, validated: BaseModel) -> Any:
        def call() -> Any:
            self.faults.maybe_fail(spec.name, self.timeout_s)
            return spec.func(validated)

        future = _EXECUTOR.submit(call)
        try:
            return future.result(timeout=self.timeout_s)
        except FutureTimeout as exc:
            # The worker thread cannot be killed; the result is discarded when it finishes.
            raise TransientToolError(f"{spec.name} timed out after {self.timeout_s}s") from exc
        except ToolInvocationError:
            raise
        except Exception as exc:  # unexpected integration bug: do not retry blindly
            raise PermanentToolError(f"{spec.name} failed: {type(exc).__name__}: {exc}") from exc


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
