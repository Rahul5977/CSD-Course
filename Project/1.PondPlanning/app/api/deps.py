"""Shared router dependencies.

Small by design. Anything that grows logic belongs in an engine, not here. The
port factories are cached per process so every request shares one adapter
bundle — one connection pool, one object-store client.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Query, Response

from app.core.config import Settings, get_settings
from app.jobs.runner import JobRunner, build_job_runner
from app.providers.fixtures import FIXTURE_HEADER
from app.providers.rainfall.service import build_rainfall_provider
from app.providers.resilience import FallbackChain
from app.providers.storage import ObjectStore, build_object_store
from app.repositories import Repositories, build_repositories


def mark_fixture(response: Response) -> None:
    """Stamp a response as fixture scaffolding.

    Declared as a dependency rather than written into each handler so that no
    fixture route can forget it, and so that deleting one line removes the mark
    when the real engine lands.
    """
    response.headers[FIXTURE_HEADER] = "true"


#: Applied to every route still backed by the fixture provider.
FixtureRoute = Depends(mark_fixture)


class Pagination:
    """Limit/offset paging, shared by every collection route."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        """Capture the validated paging window."""
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]


@lru_cache(maxsize=1)
def get_repositories() -> Repositories:
    """The persistence adapters named in settings."""
    return build_repositories(get_settings())


@lru_cache(maxsize=1)
def get_object_store() -> ObjectStore:
    """The object-store adapter named in settings."""
    return build_object_store(get_settings())


@lru_cache(maxsize=1)
def get_job_runner() -> JobRunner:
    """The job runner named in settings."""
    return build_job_runner(get_settings())


@lru_cache(maxsize=1)
def get_rainfall_chain() -> FallbackChain:
    """The rainfall provider stack named in settings."""
    return build_rainfall_provider(get_settings(), get_object_store())


def reset_dependency_caches() -> None:
    """Forget cached adapters (tests that change settings)."""
    get_repositories.cache_clear()
    get_object_store.cache_clear()
    get_job_runner.cache_clear()
    get_rainfall_chain.cache_clear()


ReposDep = Annotated[Repositories, Depends(get_repositories)]
StoreDep = Annotated[ObjectStore, Depends(get_object_store)]
RunnerDep = Annotated[JobRunner, Depends(get_job_runner)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RainfallDep = Annotated[FallbackChain, Depends(get_rainfall_chain)]
