from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.api.dependencies import ContainerDep, PrincipalDep
from app.api.schemas import HealthOut, PrincipalOut
from app.observability.tracing import langsmith_enabled
from app.security.policy import ROLE_PERMISSIONS

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, summary="Application health")
def health(c: ContainerDep) -> HealthOut:
    database = c.db.ping()
    return HealthOut(
        status="ok" if database else "degraded",
        version=__version__,
        database=database,
        model=c.service.model.label,
        checkpointer=c.settings.checkpointer,
        langsmith_tracing=langsmith_enabled(),
    )


@router.get("/api/v1/me", response_model=PrincipalOut, summary="Current API principal")
def me(principal: PrincipalDep) -> PrincipalOut:
    return PrincipalOut(
        subject=principal.subject,
        role=principal.role.value,
        permissions=sorted(p.value for p in ROLE_PERMISSIONS[principal.role]),
    )
