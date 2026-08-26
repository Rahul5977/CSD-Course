"""Build the workflow context from settings — shared by the API and the worker."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.engines.workflows.contour_analysis import WorkflowContext
from app.providers.geocoding import reverse_geocode
from app.providers.storage import build_object_store
from app.repositories import build_repositories


def build_context(settings: Settings) -> WorkflowContext:
    """Wire adapters to ports according to settings."""
    return WorkflowContext(
        repos=build_repositories(settings),
        store=build_object_store(settings),
        default_floor_m=settings.default_dem_floor_m,
        tiles_public_base=settings.tiles_public_base,
        geocode=reverse_geocode if settings.geocode_enabled else None,
    )


@lru_cache(maxsize=1)
def get_context() -> WorkflowContext:
    """Process-wide context (the adapters hold connections; build them once)."""
    return build_context(get_settings())
