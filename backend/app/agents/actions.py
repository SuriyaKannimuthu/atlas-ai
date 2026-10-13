"""Action layer: deterministic policy gate and idempotent execution of approved actions."""

from __future__ import annotations

from typing import Any

from app.graph.context import WorkflowContext
from app.security.policy import classify_action
from app.tools.base import ToolInvocationError

AGENT = "action_executor"


def policy_gate(state: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    """Classify proposed actions. Unknown action types are dropped, never executed."""
    emit = ctx.emitter("policy_gate")
    classified = []
    for action in state.get("proposed_actions", []):
        policy = classify_action(action["type"])
        if policy is None:
            emit(
                "action_blocked",
                {
                    "action_id": action["id"],
                    "type": action["type"],
                    "reason": "action type not permitted by policy",
                },
            )
            continue
        classified.append(
            {
                **action,
                "requires_approval": policy.requires_approval,
                "risk": policy.risk.value,
                "tool": policy.tool,
                "description": policy.description,
            }
        )
    pending = [a for a in classified if a["requires_approval"]]
    return {
        "proposed_actions": classified,
        "approval_status": "pending" if pending else "not_required",
    }


def execute(state: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    emit = ctx.emitter(AGENT)
    approved = state.get("approval_status") == "approved"
    results = []
    for action in state.get("proposed_actions", []):
        if action["requires_approval"] and not approved:
            results.append(
                {
                    "action_id": action["id"],
                    "type": action["type"],
                    "status": "skipped",
                    "reason": f"approval {state['approval_status']}",
                }
            )
            continue
        # Stable per incident and action: a resumed or retried workflow cannot act twice.
        key = f"{state['incident_id']}:{action['id']}"
        try:
            outcome = ctx.call_tool(
                AGENT, action["tool"], {**action["params"], "idempotency_key": key}
            )
            results.append(
                {
                    "action_id": action["id"],
                    "type": action["type"],
                    "status": "executed",
                    "idempotency_key": key,
                    "result": outcome,
                }
            )
        except ToolInvocationError as exc:
            emit("action_failed", {"action_id": action["id"], "error": str(exc)[:300]})
            results.append(
                {
                    "action_id": action["id"],
                    "type": action["type"],
                    "status": "failed",
                    "idempotency_key": key,
                    "error": str(exc)[:300],
                }
            )
    return {"action_results": results}
