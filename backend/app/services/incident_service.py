"""Incident lifecycle: submission, background execution, approval resumption, cancellation.

Status machine (enforced with conditional updates in the repository):

    queued -> running -> awaiting_approval -> running -> completed
                     \\-> completed | failed | cancelled
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.config import Settings
from app.graph.context import (
    WorkflowBudgetExceededError,
    WorkflowCancelledError,
    WorkflowContext,
)
from app.graph.state import initial_state
from app.observability.tracing import run_config
from app.persistence.models import Incident, utcnow
from app.persistence.repository import IncidentRepository
from app.security.policy import Principal
from app.services.model_gateway import ModelGateway
from app.tools.base import CallBudget, ToolRegistry

log = logging.getLogger(__name__)

TERMINAL = frozenset({"completed", "failed", "cancelled"})
RESUMABLE = frozenset({"queued", "running"})


class ConflictError(Exception):
    """The requested transition is not valid for the incident's current state."""


class NotFoundError(Exception):
    pass


class ForbiddenError(Exception):
    pass


class IncidentService:
    def __init__(
        self,
        settings: Settings,
        repo: IncidentRepository,
        graph: CompiledStateGraph,
        tools: ToolRegistry,
        model: ModelGateway,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.graph = graph
        self.tools = tools
        self.model = model
        self._executor = (
            ThreadPoolExecutor(settings.worker_threads, thread_name_prefix="atlas-workflow")
            if settings.executor == "thread"
            else None
        )
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # --- commands ----------------------------------------------------------------------

    def submit(self, principal: Principal, description: str, hints: dict[str, Any]) -> Incident:
        incident = self.repo.create_incident(
            description=description,
            service_name=hints.get("service_name"),
            deployment_id=hints.get("deployment_id"),
            severity=hints.get("severity"),
            created_by=principal.subject,
        )
        self.repo.audit(principal.subject, "incident.submitted", incident.id, {"hints": hints})
        self.repo.add_event(incident.id, "workflow_queued", None, {"by": principal.subject})
        self._dispatch(incident.id, resume=None)
        return self.repo.get(incident.id) or incident

    def decide(
        self, principal: Principal, incident_id: str, decision: str, comment: str | None
    ) -> Incident:
        incident = self._require(incident_id)
        approval = self.repo.pending_approval(incident_id)
        if incident.status != "awaiting_approval" or approval is None:
            raise ConflictError("incident has no pending approval")
        if self.settings.require_separation_of_duties and incident.created_by == principal.subject:
            raise ForbiddenError("the submitter of an incident may not approve its actions")
        if not self.repo.decide_approval(approval.id, decision, principal.subject, comment):
            raise ConflictError("approval was already decided")

        self.repo.audit(
            principal.subject,
            f"approval.{decision}",
            incident_id,
            {
                "approval_id": approval.id,
                "comment": comment,
                "actions": [a["id"] for a in approval.actions],
            },
        )
        self.repo.add_event(
            incident_id,
            "approval_decided",
            "human_approval",
            {"approval_id": approval.id, "decision": decision, "by": principal.subject},
        )
        self.repo.transition(incident_id, ["awaiting_approval"], "running")
        self._dispatch(
            incident_id,
            resume={
                "decision": decision,
                "decided_by": principal.subject,
                "comment": comment,
                "approval_id": approval.id,
            },
        )
        return self._require(incident_id)

    def cancel(self, principal: Principal, incident_id: str) -> Incident:
        incident = self._require(incident_id)
        if incident.status in TERMINAL:
            raise ConflictError(f"incident is already {incident.status}")
        self.repo.audit(principal.subject, "incident.cancel_requested", incident_id)
        if self.repo.transition(
            incident_id, ["queued", "awaiting_approval"], "cancelled", completed_at=utcnow()
        ):
            self.repo.expire_approvals(incident_id)
            self.repo.add_event(incident_id, "workflow_cancelled", None, {"by": principal.subject})
        else:
            # Running: the next node boundary observes the flag and stops cleanly.
            self.repo.update(incident_id, cancel_requested=True)
            self.repo.add_event(incident_id, "cancel_requested", None, {"by": principal.subject})
        return self._require(incident_id)

    def recover(self) -> int:
        """Resume investigations interrupted by a restart, from their last checkpoint."""
        interrupted = self.repo.with_status(RESUMABLE)
        for incident in interrupted:
            self.repo.add_event(incident.id, "workflow_recovered", None, {})
            self._dispatch(incident.id, resume=None)
        return len(interrupted)

    def shutdown(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    # --- execution ---------------------------------------------------------------------

    def _dispatch(self, incident_id: str, resume: dict[str, Any] | None) -> None:
        if self._executor is None:
            self._run(incident_id, resume)
        else:
            self._executor.submit(self._run_safely, incident_id, resume)

    def _run_safely(self, incident_id: str, resume: dict[str, Any] | None) -> None:
        try:
            self._run(incident_id, resume)
        except Exception:  # never let a worker thread die silently
            log.exception("workflow crashed for %s", incident_id)

    def _run(self, incident_id: str, resume: dict[str, Any] | None) -> None:
        with self._lock_for(incident_id):
            incident = self.repo.get(incident_id)
            if incident is None or incident.status in TERMINAL:
                return
            config = run_config(incident_id, self.settings, self.model.label)
            has_checkpoint = bool(self.graph.get_state(config).values)
            if resume is not None:
                graph_input: Any = Command(resume=resume)
            elif has_checkpoint:
                graph_input = None  # continue from the last checkpoint
            else:
                graph_input = initial_state(
                    incident_id,
                    incident.description,
                    {
                        "service_name": incident.service_name,
                        "deployment_id": incident.deployment_id,
                        "severity": incident.severity,
                    },
                )

            self.repo.transition(incident_id, ["queued", "running"], "running")
            self.repo.add_event(
                incident_id,
                "workflow_started",
                None,
                {"resumed": has_checkpoint, "model": self.model.label},
            )
            ctx = self._context(incident_id)
            started = time.perf_counter()
            try:
                self.graph.invoke(graph_input, config, context=ctx)
            except WorkflowCancelledError:
                self.repo.update(
                    incident_id, status="cancelled", completed_at=utcnow(), current_node=None
                )
                self.repo.add_event(incident_id, "workflow_cancelled", None, {})
            except WorkflowBudgetExceededError as exc:
                self._fail(incident_id, f"budget exceeded: {exc}")
            except Exception as exc:
                log.exception("workflow failed for %s", incident_id)
                self._fail(incident_id, f"{type(exc).__name__}: {exc}")
            else:
                self._after_run(incident_id, config)
            finally:
                self._record_metrics(incident_id, ctx, time.perf_counter() - started)

    def _after_run(self, incident_id: str, config: Any) -> None:
        snapshot = self.graph.get_state(config)
        values = snapshot.values
        report = values.get("final_report")
        if snapshot.interrupts:
            request = snapshot.interrupts[0].value
            approval = self.repo.create_approval(incident_id, request["actions"])
            self.repo.update(
                incident_id,
                status="awaiting_approval",
                report=report,
                current_node="human_approval",
            )
            self.repo.add_event(
                incident_id,
                "approval_requested",
                "human_approval",
                {"approval_id": approval.id, "actions": [a["id"] for a in request["actions"]]},
            )
            return

        final = dict(report or {})
        final["actions"] = _merge_action_outcomes(
            values.get("proposed_actions", []), values.get("action_results", [])
        )
        final["approval"] = values.get("approval")
        self.repo.update(
            incident_id, status="completed", report=final, completed_at=utcnow(), current_node=None
        )
        self.repo.add_event(
            incident_id,
            "workflow_completed",
            None,
            {"status": final.get("status"), "rounds": values.get("round")},
        )

    def _fail(self, incident_id: str, error: str) -> None:
        self.repo.update(incident_id, status="failed", error=error[:2000], completed_at=utcnow())
        self.repo.add_event(incident_id, "workflow_failed", None, {"error": error[:500]})

    def _context(self, incident_id: str) -> WorkflowContext:
        def record(event_type: str, node: str | None, payload: dict[str, Any]) -> None:
            self.repo.add_event(incident_id, event_type, node, payload)

        return WorkflowContext(
            incident_id=incident_id,
            settings=self.settings,
            tools=self.tools,
            model=self.model,
            record_event=record,
            is_cancel_requested=lambda: self.repo.is_cancel_requested(incident_id),
            on_node_start=lambda node: self.repo.update(incident_id, current_node=node),
            budget=CallBudget(limit=self.settings.max_tool_calls),
        )

    def _record_metrics(self, incident_id: str, ctx: WorkflowContext, elapsed_s: float) -> None:
        incident = self.repo.get(incident_id)
        previous = (incident.metrics if incident else None) or {}
        self.repo.merge_metrics(
            incident_id,
            {
                "execution_ms": previous.get("execution_ms", 0) + int(elapsed_s * 1000),
                "tool_calls": previous.get("tool_calls", 0) + ctx.budget.used,
                "model_calls": previous.get("model_calls", 0) + ctx.usage.get("model_calls", 0),
                "input_tokens": previous.get("input_tokens", 0) + ctx.usage.get("input_tokens", 0),
                "output_tokens": previous.get("output_tokens", 0)
                + ctx.usage.get("output_tokens", 0),
                "model": self.model.label,
            },
        )

    # --- helpers -----------------------------------------------------------------------

    def _require(self, incident_id: str) -> Incident:
        incident = self.repo.get(incident_id)
        if incident is None:
            raise NotFoundError(incident_id)
        return incident

    def _lock_for(self, incident_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(incident_id, threading.Lock())


def _merge_action_outcomes(
    proposed: list[dict[str, Any]], results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {r["action_id"]: r for r in results}
    return [{**action, "outcome": by_id.get(action["id"])} for action in proposed]
