"""Investigation Planner: turn the incident spec (and any review gaps) into bounded steps.

Planning is deterministic on purpose. It decides which evidence sources to query, never runs
more than one step per agent per round, never repeats a completed step, and stops when the
round budget is spent - which is what keeps the review loop from running away.
"""

from __future__ import annotations

from typing import Any

from app.agents.schemas import IncidentSpec, PlanStep
from app.graph.context import WorkflowContext

# Map review gaps to the step that can close them. `dependency_health` has no tool yet, so it
# is reported as an open question instead of being planned.
GAP_TO_STEP: dict[str, tuple[str, str, str]] = {
    "logs": ("log_analysis", "default", "Re-query logs for the incident window."),
    "logs_wide": (
        "log_analysis",
        "wide",
        "Widen the log window to check whether the pattern predates the incident.",
    ),
    "code": ("code_analysis", "default", "Inspect changes shipped near the incident."),
    "previous_deployments": (
        "code_analysis",
        "wide",
        "Inspect earlier deployments for related changes.",
    ),
    "knowledge": (
        "knowledge_retrieval",
        "wide",
        "Search runbooks and postmortems for the observed error signatures.",
    ),
}


def run(state: dict[str, Any], ctx: WorkflowContext) -> dict[str, Any]:
    round_ = state.get("round", 0) + 1
    plan = next_steps(state, round_)
    ctx.emitter("plan")(
        "plan_created",
        {
            "round": round_,
            "steps": [{"id": s["id"], "agent": s["agent"], "mode": s["mode"]} for s in plan],
        },
    )
    return {"investigation_plan": plan, "round": round_}


def next_steps(state: dict[str, Any], round_: int) -> list[dict[str, Any]]:
    """Steps for `round_`: at most one per agent, never repeating a completed step."""
    spec = IncidentSpec.model_validate(state["incident_spec"])
    done = {
        _signature(step)
        for step in state.get("completed_steps", [])
        if step.get("status") != "failed"
    }

    if round_ == 1:
        candidates = initial_steps(spec)
    else:
        gaps = (state.get("review") or {}).get("missing_evidence", [])
        candidates = [
            PlanStep(id="", agent=agent, mode=mode, objective=objective)  # type: ignore[arg-type]
            for gap in gaps
            if gap in GAP_TO_STEP
            for agent, mode, objective in [GAP_TO_STEP[gap]]
        ]

    plan: list[dict[str, Any]] = []
    seen_agents: set[str] = set()
    for step in candidates:
        if step.agent in seen_agents or (step.agent, step.mode) in done:
            continue
        seen_agents.add(step.agent)
        step.id = f"r{round_}-{step.agent}"
        plan.append(step.model_dump())
    return plan


def initial_steps(spec: IncidentSpec) -> list[PlanStep]:
    steps = [
        PlanStep(
            id="",
            agent="log_analysis",
            objective="Quantify error and latency changes and cluster error signatures.",
        ),
    ]
    if spec.service_name:
        steps.append(
            PlanStep(
                id="",
                agent="code_analysis",
                objective=(
                    f"Inspect commits shipped in {spec.deployment_id}."
                    if spec.deployment_id
                    else "Check whether any deployment preceded the incident."
                ),
            )
        )
    steps.append(
        PlanStep(
            id="",
            agent="knowledge_retrieval",
            objective="Find runbooks and prior incidents matching the symptoms.",
        )
    )
    return steps


def _signature(step: dict[str, Any]) -> tuple[str, str]:
    return step.get("agent", ""), step.get("mode", "default")
