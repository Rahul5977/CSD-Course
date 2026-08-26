"""Twelve-factor configuration.

Every deployment-varying value is read from the environment exactly once, at
import time, into a single frozen ``Settings`` object. Nothing else in the
codebase calls ``os.environ`` — that is what makes the same image runnable in
Docker, in CI and on a laptop without code changes.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from the environment or a local ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="POND_",
        extra="ignore",
        frozen=True,
    )

    # -- application -----------------------------------------------------
    app_name: str = "AI-based Village Pond Planning System"
    env: Literal["local", "ci", "docker", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # -- observability ---------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    # -- postgres --------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "pond"
    postgres_password: str = "pond"
    postgres_db: str = "pond"

    # -- redis -----------------------------------------------------------
    redis_host: str = "localhost"
    redis_port: int = 6379

    # -- wiring: which adapter behind each port ---------------------------
    # The same code runs in three configurations — Docker (postgres, celery,
    # minio), a laptop without Docker (memory, inline, local) and CI. Choosing
    # adapters here, not with conditionals in the code, is what keeps that true.
    persistence: Literal["postgres", "memory"] = "postgres"
    job_runner: Literal["celery", "inline"] = "celery"
    object_store: Literal["minio", "local"] = "minio"
    local_store_dir: str = "data/cache/store"

    # -- minio / s3 --------------------------------------------------------
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "pond"
    minio_secret_key: str = "pondpond"
    minio_bucket: str = "pond"
    minio_secure: bool = False

    # -- tiles -------------------------------------------------------------
    # Public prefix the browser uses to reach TiTiler (nginx proxies it).
    tiles_public_base: str = "/tiles"

    # -- analysis defaults ------------------------------------------------
    # Deliberately *defaults*, not constants: every one of these can be
    # overridden per request, and none of them is specific to any one input
    # map. See docs/ROADMAP.md §6, "derive everything from the input".
    max_upload_mb: int = Field(default=64, ge=1, le=512)
    pour_point_snap_radius_m: float = Field(default=150.0, gt=0)
    # Finest DEM cell size when an upload does not identify its source DEM.
    default_dem_floor_m: float = Field(default=10.0, gt=0)
    # Reverse-geocode the AOI centroid to name the village. Off in CI.
    geocode_enabled: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """SQLAlchemy URL for the psycopg3 driver."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """Redis URL used by the cache and the job queue."""
        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so the environment is read once. Tests that need different values
    call ``get_settings.cache_clear()`` after patching the environment.
    """
    return Settings()
