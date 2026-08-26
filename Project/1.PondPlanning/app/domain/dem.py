"""The elevation-source boundary: what any DEM provider must produce.

Strategy/port: the hydrology engine consumes a :class:`DEMProduct` and does not
care whether it came from an uploaded contour map or a downloaded tile mosaic.
That indifference is what lets the Phase 2 route and a future provider-DEM path
share one validated chain (ADR 0011).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.domain.raster import Raster

ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True, slots=True)
class DEMProvenance:
    """Where the elevations came from, and how much to trust them.

    ``assumed`` is True when the source could not be identified and the
    accuracy figures are conservative defaults rather than published values.
    """

    source: str
    native_resolution_m: float
    vertical_accuracy_relative_m: float
    vertical_accuracy_absolute_m: float
    attribution: tuple[str, ...]
    acquired: str | None = None
    assumed: bool = False


@dataclass(frozen=True, slots=True)
class DEMProduct:
    """A working DEM plus everything needed to report on it honestly."""

    raster: Raster
    provenance: DEMProvenance
    working_resolution_m: float
    method: str
    warnings: tuple[tuple[str, str, str], ...] = ()  # (code, message, severity)
    details: dict[str, Any] = field(default_factory=dict)


class DEMProvider(Protocol):
    """Anything that can yield a working DEM for an area of interest."""

    @property
    def name(self) -> str:
        """Short adapter name, recorded in the job result."""
        ...

    def produce(self, on_progress: ProgressCallback | None = None) -> DEMProduct:
        """Build the DEM, reporting coarse progress as (percent, stage)."""
        ...
