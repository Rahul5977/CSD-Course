"""Resilience decorators for external providers: Retry, CircuitBreaker, Cached, FallbackChain.

Each is a small, framework-free class wrapping a :class:`RainfallProvider`;
they compose by nesting, so the production stack reads exactly as the design
says: ``FallbackChain([Cached(CircuitBreaker(Retry(open_meteo))), ...])``.

- **Retry** — a transient network error is retried with jittered backoff.
- **CircuitBreaker** — after ``failures`` consecutive errors the provider is
  skipped for ``reset_s`` seconds, so a dead API costs one timeout, not one
  per request. Half-open after the window: one trial call.
- **Cached** — the last good record for a point is kept in the object store;
  served if fresh, or as a stale fallback when every live provider fails —
  the behaviour the chaos test exercises.
- **FallbackChain** — tries providers in order and records which one answered.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date

import numpy as np

from app.core.observability import CACHE_EVENTS, PROVIDER_ERRORS
from app.domain.errors import UpstreamUnavailableError
from app.domain.rainfall import DailyRainfall, RainfallProvider
from app.providers.storage import ObjectStore

logger = logging.getLogger(__name__)


class Retry:
    """Retry transient failures with exponential backoff and jitter."""

    def __init__(
        self,
        inner: RainfallProvider,
        attempts: int = 3,
        base_delay_s: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Wrap ``inner``; ``sleep`` is injectable so tests do not wait."""
        self._inner, self._attempts, self._base, self._sleep = inner, attempts, base_delay_s, sleep

    @property
    def name(self) -> str:
        """Delegates to the wrapped provider."""
        return self._inner.name

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """Try up to ``attempts`` times."""
        last: Exception | None = None
        for attempt in range(self._attempts):
            try:
                return self._inner.daily(lon, lat, start, end)
            except UpstreamUnavailableError as exc:
                last = exc
                PROVIDER_ERRORS.labels(self.name).inc()
                if attempt < self._attempts - 1:
                    self._sleep(self._base * (2**attempt) * (0.5 + random.random()))
        assert last is not None
        raise last


@dataclass
class _BreakerState:
    failures: int = 0
    opened_at: float | None = None
    stats: dict[str, int] = field(default_factory=lambda: {"opened": 0, "short_circuited": 0})


class CircuitBreaker:
    """Skip a provider that keeps failing; probe it again after ``reset_s``."""

    def __init__(
        self,
        inner: RainfallProvider,
        failures: int = 5,
        reset_s: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Wrap ``inner``; ``clock`` is injectable for tests."""
        self._inner, self._threshold, self._reset, self._clock = inner, failures, reset_s, clock
        self.state = _BreakerState()

    @property
    def name(self) -> str:
        """Delegates to the wrapped provider."""
        return self._inner.name

    @property
    def is_open(self) -> bool:
        """True while the breaker refuses calls."""
        opened = self.state.opened_at
        return opened is not None and (self._clock() - opened) < self._reset

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """Call through unless open; one trial call when half-open."""
        if self.is_open:
            self.state.stats["short_circuited"] += 1
            msg = f"{self.name}: circuit open after {self.state.failures} failures"
            raise UpstreamUnavailableError(msg, {"provider": self.name, "circuit": "open"})
        try:
            result = self._inner.daily(lon, lat, start, end)
        except UpstreamUnavailableError:
            self.state.failures += 1
            if self.state.failures >= self._threshold:
                self.state.opened_at = self._clock()
                self.state.stats["opened"] += 1
                logger.warning("circuit opened", extra={"provider": self.name})
            raise
        self.state.failures = 0
        self.state.opened_at = None
        return result


class Cached:
    """Object-store cache of the last good record per (provider, point, range).

    ``ttl_s`` decides freshness. A fresh entry is served as current data; a
    stale one is still returned when the live call fails — flagged
    ``fetched_live=False`` so the API can say "cached, provider unreachable".
    """

    def __init__(
        self, inner: RainfallProvider, store: ObjectStore, ttl_s: float = 86_400.0
    ) -> None:
        """Wrap ``inner`` with ``store`` as the cache."""
        self._inner, self._store, self._ttl = inner, store, ttl_s

    @property
    def name(self) -> str:
        """Delegates to the wrapped provider."""
        return self._inner.name

    def key(self, lon: float, lat: float, start: date, end: date) -> str:
        """Cache key: provider + point rounded to ~100 m + range."""
        return (
            f"rainfall/{self.name}/{lat:.3f}_{lon:.3f}/{start.isoformat()}_{end.isoformat()}.json"
        )

    def _read(self, key: str) -> tuple[DailyRainfall, float] | None:
        if not self._store.exists(key):
            return None
        doc = json.loads(self._store.get(key))
        record = DailyRainfall(
            days=np.array(doc["days"], dtype="datetime64[D]"),
            mm=np.array(doc["mm"], dtype=np.float64),
            source=doc["source"],
            grid_label=doc["grid_label"],
            latitude=doc["latitude"],
            longitude=doc["longitude"],
            attribution=doc["attribution"],
            fetched_live=False,
        )
        return record, float(doc["stored_at"])

    def _write(self, key: str, record: DailyRainfall) -> None:
        doc = {
            "days": record.days.astype("datetime64[D]").astype(str).tolist(),
            "mm": [None if np.isnan(v) else float(v) for v in record.mm],
            "source": record.source,
            "grid_label": record.grid_label,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "attribution": record.attribution,
            "stored_at": time.time(),
        }
        self._store.put(key, json.dumps(doc).encode(), "application/json")

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """Fresh cache → live call (and refresh) → stale cache → error."""
        key = self.key(lon, lat, start, end)
        cached = self._read(key)
        if cached is not None and time.time() - cached[1] < self._ttl:
            # A fresh cache entry *is* current data; only a stale one is a fallback.
            CACHE_EVENTS.labels("rainfall", "hit").inc()
            return replace(cached[0], fetched_live=True)
        try:
            record = self._inner.daily(lon, lat, start, end)
        except UpstreamUnavailableError:
            if cached is not None:
                logger.warning("serving stale rainfall cache", extra={"key": key})
                CACHE_EVENTS.labels("rainfall", "stale").inc()
                return cached[0]
            CACHE_EVENTS.labels("rainfall", "miss").inc()
            raise
        CACHE_EVENTS.labels("rainfall", "miss").inc()
        self._write(key, record)
        return record


class FallbackChain:
    """Try providers in order; the first success wins and is recorded."""

    def __init__(self, providers: list[RainfallProvider]) -> None:
        """Order matters: primary first."""
        self._providers = providers
        self.last_used: str | None = None
        self.last_errors: list[str] = []

    @property
    def name(self) -> str:
        """Names of the chain members."""
        return " → ".join(p.name for p in self._providers)

    def daily(self, lon: float, lat: float, start: date, end: date) -> DailyRainfall:
        """First provider that answers; raises with every error if none does."""
        errors: list[str] = []
        for provider in self._providers:
            try:
                record = provider.daily(lon, lat, start, end)
            except UpstreamUnavailableError as exc:
                errors.append(f"{provider.name}: {exc.message}")
                continue
            self.last_used = provider.name
            self.last_errors = errors
            return record
        self.last_errors = errors
        msg = "every rainfall provider failed"
        raise UpstreamUnavailableError(msg, {"errors": errors})
