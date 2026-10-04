"""Health and readiness response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness answer: the process is up and serving."""

    status: Literal["ok"] = "ok"
    app: str = Field(description="Human-readable application name")
    version: str = Field(description="Application version, semver")
    env: str = Field(description="Deployment environment this process believes it is in")


class DependencyStatus(BaseModel):
    """Reachability of one backing service."""

    name: str
    reachable: bool
    detail: str | None = Field(default=None, description="Error text when unreachable")


class ReadinessResponse(BaseModel):
    """Readiness answer: every dependency needed to serve real traffic is reachable.

    Kept distinct from liveness on purpose — an orchestrator should restart a
    process that fails liveness, but only stop routing traffic to one that fails
    readiness. Conflating them turns a slow database into a restart loop.
    """

    status: Literal["ready", "degraded"]
    dependencies: list[DependencyStatus]
