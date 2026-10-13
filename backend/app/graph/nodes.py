"""Graph nodes: thin, instrumented adapters around the agents."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from typing import Any

from langgraph.errors import GraphBubbleUp
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app.agents import (
    actions,
    code_analysis,
    knowledge_retrieval,
    log_analysis,
    planner,
    reporting,
    root_cause_review,
    triage,
)
from app.graph.context import WorkflowContext
from app.tools.base import ToolInvocationError

AgentFn = Callable[[dict[str, Any], WorkflowContext], dict[str, Any]]


def instrumented(name: str, fn: AgentFn) -> Callable[..., dict[str, Any]]:
    """Wrap an agent as a node: enforce cancellation and time budgets, record timing events.

    The wrapper's own signature (`state, runtime`) is what LangGraph inspects to inject the
    runtime context, so it deliberately does not use functools.wraps.
    """

    def node(state: dict[str, Any], runtime: Runtime[WorkflowContext]) -> dict[str, Any]:
        ctx = runtime.context
        ctx.check_limits()
        ctx.on_node_start(name)
        step = state.get("step", {}).get("id") if isinstance(state.get("step"), dict) else None
        ctx.record_event("node_started", name, {"step": step} if step else {})
        started = time.perf_counter()
        try:
            update = fn(state, ctx)
        except GraphBubbleUp:  # interrupts and other control flow, not failures
            raise
        except Exception as exc:
            ctx.record_event(
                "node_failed",
                name,
                {"error": f"{type(exc).__name__}: {exc}"[:500], "duration_ms": _ms(started)},
            )
            raise
        ctx.record_event(
            "node_completed",
            name,
            {"duration_ms": _ms(started), "updated": sorted(update or {}), **_summary(update)},
        )
        return update

    node.__name__ = f"{name}_node"
    return node


def degrade_gracefully(fn: AgentFn) -> AgentFn:
    """A failed evidence source should weaken the investigation, not abort it."""

    def run(task: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
        try:
            return fn(task, ctx)
        except ToolInvocationError as exc:
            step = task["step"]
            ctx.record_event(
                "step_failed", step["agent"], {"step": step["id"], "error": str(exc)[:300]}
            )
            return {
                "evidence": [],
                "completed_steps": [
                    {
                        "id": step["id"],
                        "agent": step["agent"],
                        "mode": step["mode"],
                        "status": "failed",
                        "evidence_count": 0,
                        "note": str(exc)[:300],
                    }
                ],
            }

    return run


def aggregate(state: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    """Join point after parallel investigation; reports evidence coverage for this round."""
    round_ = state.get("round", 1)
    this_round = [e for e in state.get("evidence", []) if e.get("round") == round_]
    ctx.emitter("aggregate")(
        "evidence_aggregated",
        {
            "round": round_,
            "new_items": len(this_round),
            "total_items": len(state.get("evidence", [])),
            "by_source": dict(Counter(e["source"] for e in this_round)),
            "flagged": [e["id"] for e in this_round if e.get("flags")],
        },
    )
    return {}


def human_approval(state: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    """Pause until a human decides. Re-executed from the top on resume, so no side effects."""
    pending = [a for a in state.get("proposed_actions", []) if a["requires_approval"]]
    decision = interrupt({"type": "approval_request", "actions": pending})
    status = "approved" if decision.get("decision") == "approved" else "rejected"
    return {"approval_status": status, "approval": decision}


def _summary(update: dict[str, Any] | None) -> dict[str, Any]:
    if not update:
        return {}
    summary: dict[str, Any] = {}
    if "evidence" in update:
        summary["evidence_ids"] = [e["id"] for e in update["evidence"]]
    if "investigation_plan" in update:
        summary["plan"] = [s["id"] for s in update["investigation_plan"]]
    if "review" in update:
        summary["confidence"] = update["review"]["confidence"]
        summary["sufficient"] = update["review"]["sufficient"]
    if "incident_spec" in update:
        spec = update["incident_spec"]
        summary["spec"] = {
            k: spec.get(k) for k in ("category", "service_name", "deployment_id", "severity")
        }
    return summary


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


NODES: dict[str, AgentFn] = {
    "triage": triage.run,
    "plan": planner.run,
    "log_analysis": degrade_gracefully(log_analysis.run),
    "code_analysis": degrade_gracefully(code_analysis.run),
    "knowledge_retrieval": degrade_gracefully(knowledge_retrieval.run),
    "aggregate": aggregate,
    "review": root_cause_review.run,
    "report": reporting.run,
    "policy_gate": actions.policy_gate,
    "human_approval": human_approval,
    "execute_actions": actions.execute,
}
