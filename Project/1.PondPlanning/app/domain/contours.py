"""Contour lines as parsed from an uploaded map — the input side of the terrain engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from app.domain.errors import GeometryError

ElevationSource = Literal["z_coordinate", "extended_data", "placemark_name"]

#: Ordered as tried. The order is the whole point — see ADR 0011.
ELEVATION_STRATEGIES: tuple[ElevationSource, ...] = (
    "z_coordinate",
    "extended_data",
    "placemark_name",
)


@dataclass(frozen=True, slots=True)
class ContourLine:
    """One contour: a constant elevation and its vertices in EPSG:4326."""

    elevation: float
    coords: NDArray[np.float64]  # shape (n, 2): lon, lat
    source: ElevationSource


@dataclass(frozen=True, slots=True)
class ContourSet:
    """Every usable contour from one upload, plus what the file said about itself.

    Raises:
        GeometryError: If there are no lines.
    """

    lines: tuple[ContourLine, ...]
    elevation_source: ElevationSource
    aoi: NDArray[np.float64] | None = None  # (n, 2) lon/lat ring, if the file drew one
    metadata_text: str = ""
    skipped: int = 0
    strategy_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """A contour set with no contours is a parse failure, not an empty result."""
        if not self.lines:
            msg = "no contour lines"
            raise GeometryError(msg)

    @property
    def levels(self) -> NDArray[np.float64]:
        """Sorted distinct elevations."""
        return np.unique(np.array([line.elevation for line in self.lines], dtype=np.float64))

    @property
    def interval(self) -> float:
        """The dominant vertical spacing between levels (median of the gaps)."""
        levels = self.levels
        if levels.size < 2:
            return 0.0
        return float(np.median(np.diff(levels)))

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """``(min_lon, min_lat, max_lon, max_lat)`` over every vertex and the AOI."""
        stacked = np.vstack([line.coords for line in self.lines])
        if self.aoi is not None:
            stacked = np.vstack([stacked, self.aoi])
        return (
            float(stacked[:, 0].min()),
            float(stacked[:, 1].min()),
            float(stacked[:, 0].max()),
            float(stacked[:, 1].max()),
        )

    @property
    def centroid(self) -> tuple[float, float]:
        """Centre of the bounding box — enough to choose a UTM zone."""
        b = self.bounds
        return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)

    @property
    def vertex_count(self) -> int:
        """Total vertices across every line."""
        return int(sum(line.coords.shape[0] for line in self.lines))
