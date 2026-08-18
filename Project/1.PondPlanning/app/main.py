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
from app.api.routers import health
from app.core.config import get_settings
from app.core.logging import configure_logging

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

    # Probes stay unversioned — infrastructure consumes them, not clients.
    app.include_router(health.router)

    return app


app = create_app()
