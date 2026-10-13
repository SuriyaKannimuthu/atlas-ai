"""Run-scoped dependencies injected into every node through LangGraph's runtime context.

The context is not checkpointed: it is rebuilt each time a workflow starts or resumes.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.services.model_gateway import ModelGateway
from app.tools.base import CallBudget, ToolRegistry


class WorkflowCancelledError(Exception):
    pass


class WorkflowBudgetExceededError(Exception):
    pass


@dataclass
class WorkflowContext:
    incident_id: str
    settings: Settings
    tools: ToolRegistry
    model: ModelGateway
    record_event: Callable[[str, str | None, dict[str, Any]], None]
    is_cancel_requested: Callable[[], bool] = lambda: False
    on_node_start: Callable[[str], None] = lambda _node: None
    started_at: float = field(default_factory=time.monotonic)
    budget: CallBudget = field(default_factory=lambda: CallBudget(limit=40))
    usage: dict[str, int] = field(default_factory=dict)
    _usage_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def emitter(self, node: str) -> Callable[[str, dict[str, Any]], None]:
        """Event sink bound to a node; also accumulates model usage for cost reporting."""

        def emit(event_type: str, payload: dict[str, Any]) -> None:
            if event_type == "model_called":
                with self._usage_lock:
                    for key in ("input_tokens", "output_tokens"):
                        self.usage[key] = self.usage.get(key, 0) + int(payload.get(key) or 0)
                    self.usage["model_calls"] = self.usage.get("model_calls", 0) + 1
            self.record_event(event_type, node, payload)

        return emit

    def call_tool(self, caller: str, tool: str, args: dict[str, Any]) -> Any:
        return self.tools.invoke(caller, tool, args, emit=self.emitter(caller), budget=self.budget)

    def check_limits(self) -> None:
        if self.is_cancel_requested():
            raise WorkflowCancelledError(self.incident_id)
        elapsed = time.monotonic() - self.started_at
        if elapsed > self.settings.max_workflow_seconds:
            raise WorkflowBudgetExceededError(
                f"workflow exceeded {self.settings.max_workflow_seconds:.0f}s"
            )
