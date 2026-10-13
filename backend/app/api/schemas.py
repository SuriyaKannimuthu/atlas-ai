"""Request and response contracts for the public API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.persistence.models import ApprovalRequest, Incident, WorkflowEvent

IncidentStatus = Literal[
    "queued", "running", "awaiting_approval", "completed", "failed", "cancelled"
]


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=10, max_length=5000)
    service_name: str | None = Field(default=None, pattern=r"^[a-z0-9-]{2,64}$")
    deployment_id: str | None = Field(default=None, pattern=r"^d-\d{1,8}$")
    severity: Literal["sev1", "sev2", "sev3", "sev4"] | None = None


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=2000)


class ApprovalOut(BaseModel):
    id: str
    status: str
    actions: list[dict[str, Any]]
    requested_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    comment: str | None

    @classmethod
    def of(cls, approval: ApprovalRequest) -> ApprovalOut:
        return cls(
            id=approval.id,
            status=approval.status,
            actions=approval.actions,
            requested_at=approval.requested_at,
            decided_by=approval.decided_by,
            decided_at=approval.decided_at,
            comment=approval.comment,
        )


class IncidentSummary(BaseModel):
    id: str
    status: IncidentStatus
    description: str
    service_name: str | None
    severity: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    current_node: str | None
    report_status: str | None = None
    root_cause: str | None = None
    root_cause_kind: str | None = None
    confidence: float | None = None
    execution_ms: int | None = None

    @classmethod
    def of(cls, incident: Incident) -> IncidentSummary:
        report = incident.report or {}
        root = report.get("root_cause") or {}
        spec = report.get("incident_spec") or {}
        return cls(
            id=incident.id,
            status=incident.status,  # type: ignore[arg-type]
            description=incident.description,
            service_name=incident.service_name or spec.get("service_name"),
            severity=incident.severity or spec.get("severity"),
            created_by=incident.created_by,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            completed_at=incident.completed_at,
            current_node=incident.current_node,
            report_status=report.get("status"),
            root_cause=root.get("statement"),
            root_cause_kind=root.get("kind"),
            confidence=root.get("confidence"),
            execution_ms=(incident.metrics or {}).get("execution_ms"),
        )


class IncidentDetail(IncidentSummary):
    deployment_id: str | None
    cancel_requested: bool
    error: str | None
    metrics: dict[str, Any]
    has_report: bool
    pending_approval: ApprovalOut | None
    approvals: list[ApprovalOut]
    links: dict[str, str]


class IncidentList(BaseModel):
    items: list[IncidentSummary]
    counts: dict[str, int]


class EventOut(BaseModel):
    seq: int
    type: str
    node: str | None
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def of(cls, event: WorkflowEvent) -> EventOut:
        return cls(
            seq=event.seq,
            type=event.type,
            node=event.node,
            payload=event.payload,
            created_at=event.created_at,
        )


class EventList(BaseModel):
    items: list[EventOut]
    next_after: int


class ReportOut(BaseModel):
    incident_id: str
    final: bool = Field(description="False while actions are still awaiting approval.")
    report: dict[str, Any]


class PrincipalOut(BaseModel):
    subject: str
    role: str
    permissions: list[str]


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: bool
    model: str
    checkpointer: str
    langsmith_tracing: bool
