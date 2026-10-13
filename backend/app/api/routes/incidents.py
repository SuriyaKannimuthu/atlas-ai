from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import ContainerDep, rate_limited, require
from app.api.schemas import (
    ApprovalDecision,
    ApprovalOut,
    EventList,
    EventOut,
    IncidentCreate,
    IncidentDetail,
    IncidentList,
    IncidentStatus,
    IncidentSummary,
    ReportOut,
)
from app.persistence.models import Incident
from app.security.policy import Permission, Principal
from app.services.incident_service import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

Reader = Annotated[Principal, Depends(require(Permission.INCIDENT_READ))]
Creator = Annotated[Principal, Depends(require(Permission.INCIDENT_CREATE))]
Canceller = Annotated[Principal, Depends(require(Permission.INCIDENT_CANCEL))]
Approver = Annotated[Principal, Depends(require(Permission.ACTION_APPROVE))]


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IncidentDetail,
    dependencies=[Depends(rate_limited)],
    summary="Submit an incident investigation",
)
def create_incident(body: IncidentCreate, principal: Creator, c: ContainerDep) -> IncidentDetail:
    hints = body.model_dump(exclude={"description"}, exclude_none=True)
    incident = c.service.submit(principal, body.description, hints)
    return _detail(c, incident)


@router.get("", response_model=IncidentList, summary="List incidents")
def list_incidents(
    _: Reader,
    c: ContainerDep,
    status_filter: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> IncidentList:
    items = c.repo.list(limit=limit, status=status_filter)
    return IncidentList(
        items=[IncidentSummary.of(i) for i in items], counts=c.repo.count_by_status()
    )


@router.get("/{incident_id}", response_model=IncidentDetail, summary="Incident status")
def get_incident(incident_id: str, _: Reader, c: ContainerDep) -> IncidentDetail:
    return _detail(c, _load(c, incident_id))


@router.get("/{incident_id}/report", response_model=ReportOut, summary="Incident report")
def get_report(incident_id: str, _: Reader, c: ContainerDep) -> ReportOut:
    incident = _load(c, incident_id)
    if not incident.report:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"report not available while incident is {incident.status}"
        )
    return ReportOut(
        incident_id=incident.id, final=incident.status == "completed", report=incident.report
    )


@router.get("/{incident_id}/events", response_model=EventList, summary="Workflow events")
def get_events(
    incident_id: str,
    _: Reader,
    c: ContainerDep,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> EventList:
    _load(c, incident_id)
    events = c.repo.events(incident_id, after=after, limit=limit)
    return EventList(
        items=[EventOut.of(e) for e in events], next_after=events[-1].seq if events else after
    )


@router.post(
    "/{incident_id}/approvals",
    response_model=IncidentDetail,
    summary="Approve or reject pending actions",
)
def decide_approval(
    incident_id: str, body: ApprovalDecision, principal: Approver, c: ContainerDep
) -> IncidentDetail:
    try:
        incident = c.service.decide(principal, incident_id, body.decision, body.comment)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _detail(c, incident)


@router.post("/{incident_id}/cancel", response_model=IncidentDetail, summary="Request cancellation")
def cancel_incident(incident_id: str, principal: Canceller, c: ContainerDep) -> IncidentDetail:
    try:
        incident = c.service.cancel(principal, incident_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found") from exc
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _detail(c, incident)


def _load(c: ContainerDep, incident_id: str) -> Incident:
    incident = c.repo.get(incident_id)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "incident not found")
    return incident


def _detail(c: ContainerDep, incident: Incident) -> IncidentDetail:
    approvals = c.repo.approvals(incident.id)
    pending = next((a for a in approvals if a.status == "pending"), None)
    base = f"/api/v1/incidents/{incident.id}"
    return IncidentDetail(
        **IncidentSummary.of(incident).model_dump(),
        deployment_id=incident.deployment_id,
        cancel_requested=incident.cancel_requested,
        error=incident.error,
        metrics=incident.metrics or {},
        has_report=bool(incident.report),
        pending_approval=ApprovalOut.of(pending) if pending else None,
        approvals=[ApprovalOut.of(a) for a in approvals],
        links={
            "self": base,
            "report": f"{base}/report",
            "events": f"{base}/events",
            "approvals": f"{base}/approvals",
            "cancel": f"{base}/cancel",
        },
    )
