"""Typed workflow state.

State fields are explicit and owned by specific nodes rather than being a shared chat
history. Fields annotated with `operator.add` accumulate across parallel branches and rounds;
everything else is replaced by the node that owns it.

Ownership:
    triage              -> incident_spec
    plan                -> investigation_plan, round
    investigation nodes -> evidence, completed_steps
    review              -> review, hypotheses
    report              -> final_report, proposed_actions
    policy_gate         -> proposed_actions (classified)
    human_approval      -> approval_status, approval
    execute_actions     -> action_results
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict

MAX_EVIDENCE_PER_STEP = 12
MAX_EVIDENCE_SUMMARY = 600


class IncidentState(TypedDict):
    incident_id: str
    description: str
    hints: dict[str, Any]
    incident_spec: NotRequired[dict[str, Any]]
    round: int
    investigation_plan: NotRequired[list[dict[str, Any]]]
    completed_steps: Annotated[list[dict[str, Any]], operator.add]
    evidence: Annotated[list[dict[str, Any]], operator.add]
    hypotheses: NotRequired[list[dict[str, Any]]]
    review: NotRequired[dict[str, Any]]
    final_report: NotRequired[dict[str, Any]]
    proposed_actions: NotRequired[list[dict[str, Any]]]
    approval_status: str
    approval: NotRequired[dict[str, Any]]
    action_results: Annotated[list[dict[str, Any]], operator.add]


class InvestigationTask(TypedDict):
    """Payload sent to an investigation node for one plan step (fan-out via `Send`)."""

    incident_id: str
    round: int
    step: dict[str, Any]
    incident_spec: dict[str, Any]
    evidence: list[dict[str, Any]]


def initial_state(incident_id: str, description: str, hints: dict[str, Any]) -> IncidentState:
    return IncidentState(
        incident_id=incident_id,
        description=description,
        hints=hints,
        round=0,
        completed_steps=[],
        evidence=[],
        approval_status="not_required",
        action_results=[],
    )
