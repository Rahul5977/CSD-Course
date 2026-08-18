"""Liveness and readiness probes.

The only routes in P0 backed by real logic rather than fixtures — they are what
proves the container, the network and the database wiring actually work.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app import __version__
from app.core.config import Settings, get_settings
from app.core.db import engine
from app.schemas.health import DependencyStatus, HealthResponse, ReadinessResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Report that the process is up. Never touches a dependency."""
    settings: Settings = get_settings()
    return HealthResponse(app=settings.app_name, version=__version__, env=settings.env)


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
def ready(response: Response) -> ReadinessResponse:
    """Report whether every backing service is reachable.

    Returns ``503`` when degraded so that a load balancer can act on the status
    code without parsing the body.
    """
    dependencies = [_check_postgres()]
    all_up = all(d.reachable for d in dependencies)
    if not all_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if all_up else "degraded", dependencies=dependencies)


def _check_postgres() -> DependencyStatus:
    """Round-trip the cheapest possible query against postgres."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("readiness check failed", extra={"dependency": "postgres"})
        return DependencyStatus(name="postgres", reachable=False, detail=str(exc))
    return DependencyStatus(name="postgres", reachable=True)
