"""FastAPI dependencies: container access, authentication, authorization, rate limiting."""

from __future__ import annotations

import hmac
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from app.config import Settings
from app.persistence.database import Database
from app.persistence.repository import IncidentRepository
from app.security.policy import Permission, Principal, Role
from app.security.rate_limit import RateLimiter
from app.services.incident_service import IncidentService

log = logging.getLogger(__name__)

DEV_API_KEY = "atlas-dev-key"

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class Container:
    settings: Settings
    db: Database
    repo: IncidentRepository
    service: IncidentService
    rate_limiter: RateLimiter


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_principal(
    container: ContainerDep,
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> Principal:
    if not api_key:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    keys = container.settings.api_keys
    if not keys and container.settings.app_env == "development":
        keys = {DEV_API_KEY: {"subject": "dev-admin", "role": "admin"}}
    for candidate, entry in keys.items():
        if hmac.compare_digest(candidate.encode(), api_key.encode()):
            return Principal(subject=entry["subject"], role=Role(entry["role"]))
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED, "invalid API key", headers={"WWW-Authenticate": "ApiKey"}
    )


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require(permission: Permission) -> Callable[[Principal], Principal]:
    def check(principal: PrincipalDep) -> Principal:
        if not principal.can(permission):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"role '{principal.role}' lacks permission '{permission}'",
            )
        return principal

    return check


def rate_limited(principal: PrincipalDep, container: ContainerDep) -> None:
    allowed = container.rate_limiter.hit(
        f"submit:{principal.subject}", container.settings.rate_limit_per_minute
    )
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded", headers={"Retry-After": "60"}
        )
