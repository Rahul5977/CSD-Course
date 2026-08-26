"""Assemble the rainfall provider stack from settings.

Production: ``FallbackChain([Cached(CircuitBreaker(Retry(OpenMeteo))),
Cached(CircuitBreaker(Retry(NASAPower)))])``. Tests/offline: the recorded
adapter. One place decides; nothing else knows which.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.domain.rainfall import RainfallProvider
from app.providers.rainfall.adapters import NASAPowerAdapter, OpenMeteoAdapter, RecordedAdapter
from app.providers.resilience import Cached, CircuitBreaker, FallbackChain, Retry
from app.providers.storage import ObjectStore


def build_rainfall_provider(settings: Settings, store: ObjectStore) -> FallbackChain:
    """The provider chain named in settings, always wrapped in a FallbackChain."""
    if settings.rainfall_source == "recorded":
        return FallbackChain([RecordedAdapter(Path(settings.rainfall_recorded_path))])
    ttl = settings.rainfall_cache_ttl_s
    live: list[RainfallProvider] = [
        Cached(CircuitBreaker(Retry(OpenMeteoAdapter()), failures=3, reset_s=300), store, ttl),
        Cached(CircuitBreaker(Retry(NASAPowerAdapter()), failures=3, reset_s=300), store, ttl),
    ]
    return FallbackChain(live)
