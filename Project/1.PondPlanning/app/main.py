"""FastAPI application factory and ASGI entrypoint.

Kept to composition only — configure logging, build the app, mount routers.
No route is defined here.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.routers import (
    analysis,
    auth,
    health,
    jobs,
    meta,
    rainfall,
    recommendations,
    terrain,
    villages,
)
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.observability import install as install_observability

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Log a single startup line carrying the effective configuration."""
    settings = get_settings()
    logger.info(
        "application starting",
        extra={"env": settings.env, "version": __version__, "log_format": settings.log_format},
    )
    yield
    logger.info("application stopped")


def create_app() -> FastAPI:
    """Build the ASGI application.

    A factory rather than a module-level singleton so tests can construct an
    isolated app with patched settings.
    """
    settings = get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Terrain, catchment and runoff analysis for village pond siting. "
            "Analysis routes are asynchronous: they return 202 with a job id to poll."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    install_observability(app)

    # Probes stay unversioned — infrastructure consumes them, not clients.
    app.include_router(health.router)

    # Everything else is versioned from the first commit. Adding a version prefix
    # after clients exist is a breaking change; starting with one costs nothing.
    prefix = settings.api_v1_prefix
    for module in (villages, terrain, rainfall, recommendations, jobs, meta, auth):
        app.include_router(module.router, prefix=prefix)
    app.include_router(analysis.router, prefix=prefix)
    app.include_router(analysis.results_router, prefix=prefix)
    # The Phase 2 brief names this path; it is mounted where the brief puts it.
    app.include_router(analysis.contour_router, prefix=prefix)
    app.include_router(recommendations.exports_router, prefix=prefix)

    return app


app = create_app()
