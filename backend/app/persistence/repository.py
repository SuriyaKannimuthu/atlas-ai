"""Data access for incidents and their workflow artefacts."""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select, update

from app.persistence.database import Database
from app.persistence.models import ApprovalRequest, AuditRecord, Incident, WorkflowEvent, utcnow
from app.security.redaction import redact


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


class IncidentRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # --- incidents ---------------------------------------------------------------------

    def create_incident(self, **fields: Any) -> Incident:
        incident = Incident(id=new_id("inc"), status="queued", metrics={}, **fields)
        with self.db.session() as session:
            session.add(incident)
        return incident

    def get(self, incident_id: str) -> Incident | None:
        with self.db.session() as session:
            return session.get(Incident, incident_id)

    def list(self, *, limit: int = 50, status: str | None = None) -> list[Incident]:
        with self.db.session() as session:
            query = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
            if status:
                query = query.where(Incident.status == status)
            return list(session.scalars(query))

    def count_by_status(self) -> dict[str, int]:
        with self.db.session() as session:
            rows = session.execute(select(Incident.status, func.count()).group_by(Incident.status))
            return {status: count for status, count in rows}

    def with_status(self, statuses: Iterable[str]) -> list[Incident]:
        with self.db.session() as session:
            return list(session.scalars(select(Incident).where(Incident.status.in_(statuses))))

    def update(self, incident_id: str, **fields: Any) -> None:
        with self.db.session() as session:
            session.execute(update(Incident).where(Incident.id == incident_id).values(**fields))

    def transition(
        self, incident_id: str, from_statuses: Iterable[str], to_status: str, **fields: Any
    ) -> bool:
        """Atomically move an incident between states; False if it was not in `from_statuses`."""
        with self.db.session() as session:
            result = session.execute(
                update(Incident)
                .where(Incident.id == incident_id, Incident.status.in_(list(from_statuses)))
                .values(status=to_status, **fields)
            )
            return result.rowcount == 1

    def merge_metrics(self, incident_id: str, values: dict[str, Any]) -> None:
        with self.db.session() as session:
            incident = session.get(Incident, incident_id)
            if incident:
                incident.metrics = {**(incident.metrics or {}), **values}

    def is_cancel_requested(self, incident_id: str) -> bool:
        with self.db.session() as session:
            value = session.scalar(
                select(Incident.cancel_requested).where(Incident.id == incident_id)
            )
            return bool(value)

    # --- events ------------------------------------------------------------------------

    def add_event(
        self,
        incident_id: str,
        type_: str,
        node: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self.db.session() as session:
            session.add(
                WorkflowEvent(
                    incident_id=incident_id, type=type_, node=node, payload=redact(payload or {})
                )
            )

    def events(self, incident_id: str, *, after: int = 0, limit: int = 500) -> list[WorkflowEvent]:
        with self.db.session() as session:
            query = (
                select(WorkflowEvent)
                .where(WorkflowEvent.incident_id == incident_id, WorkflowEvent.seq > after)
                .order_by(WorkflowEvent.seq)
                .limit(limit)
            )
            return list(session.scalars(query))

    # --- approvals ---------------------------------------------------------------------

    def create_approval(self, incident_id: str, actions: list[dict[str, Any]]) -> ApprovalRequest:
        approval = ApprovalRequest(id=new_id("apr"), incident_id=incident_id, actions=actions)
        with self.db.session() as session:
            session.add(approval)
        return approval

    def pending_approval(self, incident_id: str) -> ApprovalRequest | None:
        with self.db.session() as session:
            return session.scalar(
                select(ApprovalRequest)
                .where(
                    ApprovalRequest.incident_id == incident_id, ApprovalRequest.status == "pending"
                )
                .order_by(ApprovalRequest.requested_at.desc())
            )

    def approvals(self, incident_id: str) -> list[ApprovalRequest]:
        with self.db.session() as session:
            return list(
                session.scalars(
                    select(ApprovalRequest)
                    .where(ApprovalRequest.incident_id == incident_id)
                    .order_by(ApprovalRequest.requested_at)
                )
            )

    def decide_approval(
        self, approval_id: str, decision: str, actor: str, comment: str | None
    ) -> bool:
        """Record a decision exactly once; concurrent or repeated decisions return False."""
        with self.db.session() as session:
            result = session.execute(
                update(ApprovalRequest)
                .where(ApprovalRequest.id == approval_id, ApprovalRequest.status == "pending")
                .values(status=decision, decided_by=actor, decided_at=utcnow(), comment=comment)
            )
            return result.rowcount == 1

    def expire_approvals(self, incident_id: str) -> None:
        with self.db.session() as session:
            session.execute(
                update(ApprovalRequest)
                .where(
                    ApprovalRequest.incident_id == incident_id, ApprovalRequest.status == "pending"
                )
                .values(status="expired", decided_at=utcnow())
            )

    # --- audit -------------------------------------------------------------------------

    def audit(
        self,
        actor: str,
        action: str,
        incident_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.db.session() as session:
            session.add(
                AuditRecord(
                    incident_id=incident_id,
                    actor=actor,
                    action=action,
                    details=redact(details or {}),
                )
            )

    def audit_records(self, incident_id: str) -> list[AuditRecord]:
        with self.db.session() as session:
            return list(
                session.scalars(
                    select(AuditRecord)
                    .where(AuditRecord.incident_id == incident_id)
                    .order_by(AuditRecord.id)
                )
            )
