"""Coordinate reference systems and grid georeferencing as domain concepts.

Two rules from the assignment shape this module. Nothing about any one map may
be hard-coded, so the projected CRS is *derived* from the data's own centroid
(:func:`utm_epsg_for`). And no area or distance may ever be measured in
degrees, so every grid entering a computation is checked by :func:`assert_crs`
— the classic silent failure in this class of system is a catchment "area"
computed in square degrees, which is wrong by a factor of about 1.2e10 and
looks like a plausible small number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.errors import CRSError, GeometryError


def utm_epsg_for(lon: float, lat: float) -> int:
    """Return the EPSG code of the WGS 84 / UTM zone that contains a point.

    Zones are 6° wide and numbered 1-60 eastward from 180° W; the EPSG code is
    ``326NN`` in the northern hemisphere and ``327NN`` in the southern. The
    Norway and Svalbard zone exceptions are not applied — they only exist above
    56° N, far outside any village this system will see, and applying them
    would be code nobody could justify in the viva.

    Raises:
        GeometryError: If the coordinates are outside the valid range.
    """
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        msg = "centroid outside the valid longitude/latitude range"
        raise GeometryError(msg, {"lon": lon, "lat": lat})
    zone = math.floor((lon + 180.0) / 6.0) % 60 + 1
    return (32600 if lat >= 0 else 32700) + zone


def is_utm(epsg: int) -> bool:
    """True for any WGS 84 / UTM zone code, north or south."""
    return 32601 <= epsg <= 32660 or 32701 <= epsg <= 32760


def assert_crs(epsg: int, *, expected: int | None = None) -> None:
    """Guard every computation: the grid must be in a UTM zone, in metres.

    Args:
        epsg: The EPSG code the caller believes its data is in.
        expected: When given, the exact zone the data must be in — used to
            catch two rasters from different zones being combined.

    Raises:
        CRSError: If ``epsg`` is geographic (degrees) or is not the expected zone.
    """
    if not is_utm(epsg):
        msg = f"computation requires a projected UTM grid in metres, not EPSG:{epsg}"
        raise CRSError(msg, {"epsg": epsg, "hint": "derive the zone with utm_epsg_for()"})
    if expected is not None and epsg != expected:
        msg = f"grid is in EPSG:{epsg} but EPSG:{expected} was expected"
        raise CRSError(msg, {"epsg": epsg, "expected": expected})


@dataclass(frozen=True, slots=True)
class GridSpec:
    """Georeferencing of a north-up, square-celled raster in a UTM zone.

    ``x_min``/``y_max`` are the *outer edges* of the top-left cell, GDAL
    convention, so ``cell_center(0, 0)`` is half a cell inside the corner.

    Raises:
        CRSError: If ``epsg`` is not a UTM zone.
        GeometryError: If the cell size or shape is not positive.
    """

    epsg: int
    x_min: float
    y_max: float
    cell_size: float
    rows: int
    cols: int

    def __post_init__(self) -> None:
        """Validate the CRS and the geometry once, at construction."""
        assert_crs(self.epsg)
        if self.cell_size <= 0 or self.rows <= 0 or self.cols <= 0:
            msg = "grid needs a positive cell size and shape"
            raise GeometryError(
                msg, {"cell_size": self.cell_size, "rows": self.rows, "cols": self.cols}
            )

    @property
    def x_max(self) -> float:
        """Right edge of the last column."""
        return self.x_min + self.cols * self.cell_size

    @property
    def y_min(self) -> float:
        """Bottom edge of the last row."""
        return self.y_max - self.rows * self.cell_size

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """``(x_min, y_min, x_max, y_max)`` in metres."""
        return (self.x_min, self.y_min, self.x_max, self.y_max)

    @property
    def cell_area(self) -> float:
        """Area of one cell in square metres."""
        return self.cell_size * self.cell_size

    @property
    def shape(self) -> tuple[int, int]:
        """``(rows, cols)``, numpy order."""
        return (self.rows, self.cols)

    @property
    def affine(self) -> tuple[float, float, float, float, float, float]:
        """GDAL-style affine ``(a, b, c, d, e, f)`` for raster writers."""
        return (self.cell_size, 0.0, self.x_min, 0.0, -self.cell_size, self.y_max)

    def cell_center(self, row: int, col: int) -> tuple[float, float]:
        """Projected coordinates of a cell's centre."""
        x = self.x_min + (col + 0.5) * self.cell_size
        y = self.y_max - (row + 0.5) * self.cell_size
        return (x, y)

    def contains(self, x: float, y: float) -> bool:
        """True when the point falls inside the grid's outer edges."""
        return self.x_min <= x < self.x_max and self.y_min < y <= self.y_max

    def index_of(self, x: float, y: float) -> tuple[int, int]:
        """``(row, col)`` of the cell containing a projected point.

        Raises:
            GeometryError: If the point is outside the grid.
        """
        if not self.contains(x, y):
            msg = "point is outside the analysed extent"
            raise GeometryError(msg, {"x": x, "y": y, "bounds": self.bounds})
        col = int((x - self.x_min) // self.cell_size)
        row = int((self.y_max - y) // self.cell_size)
        return (min(row, self.rows - 1), min(col, self.cols - 1))
