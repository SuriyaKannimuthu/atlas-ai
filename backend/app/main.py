"""Atlas AI API entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.dependencies import DEV_API_KEY, Container
from app.api.routes import health, incidents
from app.config import Settings, get_settings
from app.graph.checkpoint import open_checkpointer
from app.graph.workflow import build_workflow
from app.observability.tracing import configure_logging
from app.persistence.database import Database
from app.persistence.repository import IncidentRepository
from app.security.rate_limit import build_rate_limiter
from app.services.incident_service import IncidentService
from app.services.model_gateway import ModelGateway
from app.tools import build_tool_registry
from app.tools.ticketing import IdempotentStore

log = logging.getLogger("atlas")


def build_container(settings: Settings, stack: ExitStack) -> Container:
    if settings.app_env == "production" and not settings.api_keys:
        raise RuntimeError("API_KEYS must be configured in production")
    if not settings.api_keys and settings.app_env == "development":
        log.warning("No API_KEYS configured; development key %r grants admin", DEV_API_KEY)

    db = Database(settings.database_url)
    db.create_schema()
    stack.callback(db.dispose)
    repo = IncidentRepository(db)
    graph = build_workflow(
        open_checkpointer(settings, stack), max_rounds=settings.max_investigation_rounds
    )
    service = IncidentService(
        settings,
        repo,
        graph,
        build_tool_registry(settings, IdempotentStore()),
        ModelGateway(settings),
    )
    stack.callback(service.shutdown)
    return Container(settings, db, repo, service, build_rate_limiter(settings.redis_url))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with ExitStack() as stack:
            container = build_container(settings, stack)
            app.state.container = container
            recovered = container.service.recover()
            log.info(
                "Atlas AI ready (model=%s, checkpointer=%s, recovered=%d)",
                container.service.model.label,
                settings.checkpointer,
                recovered,
            )
            yield

    app = FastAPI(
        title="Atlas AI",
        version=__version__,
        description="Multi-agent incident investigation with evidence-based root-cause "
        "analysis and human-approved remediation.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"],
    )
    app.include_router(health.router)
    app.include_router(incidents.router)
    return app


app = create_app()
