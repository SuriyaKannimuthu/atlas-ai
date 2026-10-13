import time
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from app.tools.base import (
    CallBudget,
    FaultInjector,
    PermanentToolError,
    ToolBudgetExceededError,
    ToolNotPermittedError,
    ToolRegistry,
    ToolSpec,
    ToolValidationError,
    TransientToolError,
)
from app.tools.ticketing import IdempotentStore


class Args(BaseModel):
    query: str


def make_registry(func: Callable[[Any], Any], **kwargs: Any) -> ToolRegistry:
    spec = ToolSpec("knowledge.search", "test", Args, func)
    return ToolRegistry([spec], backoff_base_s=0.0, sleep=lambda _s: None, **kwargs)


def call(registry: ToolRegistry, **kwargs: Any) -> Any:
    return registry.invoke("knowledge_retrieval", "knowledge.search", {"query": "x"}, **kwargs)


def test_denies_tools_outside_the_callers_allowlist() -> None:
    events: list[str] = []
    with pytest.raises(ToolNotPermittedError):
        make_registry(lambda a: []).invoke(
            "log_analysis", "knowledge.search", {"query": "x"}, emit=lambda t, _p: events.append(t)
        )
    assert events == ["tool_denied"]


def test_validates_arguments() -> None:
    with pytest.raises(ToolValidationError):
        make_registry(lambda a: []).invoke("knowledge_retrieval", "knowledge.search", {"q": 1})


def test_retries_transient_failures() -> None:
    registry = make_registry(lambda a: ["ok"], faults=FaultInjector("knowledge.search:transient:2"))
    events: list[str] = []
    assert call(registry, emit=lambda t, _p: events.append(t)) == ["ok"]
    assert events == ["tool_retry", "tool_retry", "tool_called"]


def test_gives_up_after_max_retries() -> None:
    registry = make_registry(
        lambda a: [], max_retries=1, faults=FaultInjector("knowledge.search:transient:5")
    )
    with pytest.raises(TransientToolError):
        call(registry)


def test_does_not_retry_permanent_failures() -> None:
    calls: list[int] = []

    def boom(_args: Any) -> Any:
        calls.append(1)
        raise PermanentToolError("not found")

    with pytest.raises(PermanentToolError):
        call(make_registry(boom))
    assert len(calls) == 1


def test_unexpected_exceptions_become_permanent_errors() -> None:
    with pytest.raises(PermanentToolError):
        call(make_registry(lambda a: 1 / 0))


def test_timeouts_are_transient() -> None:
    registry = make_registry(lambda a: time.sleep(0.5), timeout_s=0.05, max_retries=0)
    with pytest.raises(TransientToolError):
        call(registry)


def test_call_budget_is_enforced() -> None:
    registry = make_registry(lambda a: [])
    budget = CallBudget(limit=1)
    call(registry, budget=budget)
    with pytest.raises(ToolBudgetExceededError):
        call(registry, budget=budget)


def test_idempotent_store_executes_once_per_key() -> None:
    store = IdempotentStore()
    assert store.run_once("inc:act", lambda: {"id": 1}) == {"id": 1, "replayed": False}
    assert store.run_once("inc:act", lambda: {"id": 2}) == {"id": 1, "replayed": True}
    assert store.execution_count == 1
