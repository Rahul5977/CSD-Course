"""Build the workflow context from settings — shared by the API and the worker."""

from __future__ import annotations

from functools import lru_cache, partial

from app.core.config import Settings, get_settings
from app.engines.workflows.contour_analysis import WorkflowContext
from app.providers.geocoding import reverse_geocode
from app.providers.rainfall.service import build_rainfall_provider
from app.providers.storage import build_object_store
from app.repositories import build_repositories


def build_context(settings: Settings) -> WorkflowContext:
    """Wire adapters to ports according to settings."""
    store = build_object_store(settings)
    return WorkflowContext(
        repos=build_repositories(settings),
        store=store,
        rainfall=build_rainfall_provider(settings, store),
        default_floor_m=settings.default_dem_floor_m,
        tiles_public_base=settings.tiles_public_base,
        geocode=(
            partial(reverse_geocode, timeout_s=settings.geocode_timeout_s)
            if settings.geocode_enabled
            else None
        ),
        stream_threshold_area_m2=settings.stream_threshold_area_m2,
        snap_radius_m=settings.pour_point_snap_radius_m,
        snap_min_upstream_area_m2=settings.snap_min_upstream_area_m2,
        siting_rise_m=settings.siting_rise_m,
        siting_top_n=settings.siting_top_n,
        siting_river_buffer_m=settings.siting_river_buffer_m,
    )


@lru_cache(maxsize=1)
def get_context() -> WorkflowContext:
    """Process-wide context (the adapters hold connections; build them once)."""
    return build_context(get_settings())
