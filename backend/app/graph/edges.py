"""Conditional routing. All routing decisions are deterministic functions of typed state."""

from __future__ import annotations

from typing import Any

from langgraph.types import Send

from app.agents.planner import next_steps
from app.config import get_settings


def route_investigations(state: dict[str, Any]) -> list[Send] | str:
    """Fan out one parallel branch per plan step; skip straight to review if nothing to do."""
    plan = state.get("investigation_plan") or []
    if not plan:
        return "aggregate"
    return [
        Send(
            step["agent"],
            {
                "incident_id": state["incident_id"],
                "round": state["round"],
                "step": step,
                "incident_spec": state["incident_spec"],
                "evidence": state.get("evidence", []),
            },
        )
        for step in plan
    ]


def route_after_review(state: dict[str, Any], max_rounds: int | None = None) -> str:
    max_rounds = max_rounds or get_settings().max_investigation_rounds
    review = state.get("review") or {}
    if review.get("sufficient") or state.get("round", 0) >= max_rounds:
        return "report"
    # Only loop when the planner can actually close a gap; otherwise report what we have.
    return "plan" if next_steps(state, state.get("round", 0) + 1) else "report"


def route_after_policy(state: dict[str, Any]) -> str:
    return "human_approval" if state.get("approval_status") == "pending" else "execute_actions"
