"""Persistence layer: ports, records, and the SQL / in-memory adapters.

:func:`build_repositories` is the one place that chooses an adapter, from
``Settings.persistence``. Everything else takes a :class:`Repositories`
bundle and does not know which one it got.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import Settings
from app.repositories.ports import DEMAssetRepository, JobRepository, VillageRepository


@dataclass(frozen=True, slots=True)
class Repositories:
    """The repository bundle handed to routers, workflows and the worker."""

    villages: VillageRepository
    jobs: JobRepository
    dem_assets: DEMAssetRepository


@lru_cache(maxsize=1)
def _memory_bundle() -> Repositories:
    from app.repositories.memory import (
        InMemoryDEMAssetRepository,
        InMemoryJobRepository,
        InMemoryVillageRepository,
    )

    return Repositories(
        villages=InMemoryVillageRepository(),
        jobs=InMemoryJobRepository(),
        dem_assets=InMemoryDEMAssetRepository(),
    )


def build_repositories(settings: Settings) -> Repositories:
    """Return the adapter bundle named in settings.

    The in-memory bundle is a process-wide singleton so that the API and an
    inline job runner in the same process see the same rows.
    """
    if settings.persistence == "memory":
        return _memory_bundle()
    from app.core.db import SessionLocal
    from app.repositories.sql import SqlDEMAssetRepository, SqlJobRepository, SqlVillageRepository

    return Repositories(
        villages=SqlVillageRepository(SessionLocal),
        jobs=SqlJobRepository(SessionLocal),
        dem_assets=SqlDEMAssetRepository(SessionLocal),
    )


def reset_memory_repositories() -> None:
    """Drop the in-memory bundle (tests)."""
    _memory_bundle.cache_clear()
