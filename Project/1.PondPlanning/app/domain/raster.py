"""A georeferenced raster as a value object.

Numpy is the one third-party import the domain layer allows itself: a raster
*is* an array with a grid attached, and modelling that without numpy would be
theatre. Nothing here knows about files, tiles or GDAL — that is provider work.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.errors import GeometryError
from app.domain.geo import GridSpec

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Raster:
    """A single-band float raster on a :class:`GridSpec`. ``NaN`` is nodata.

    Raises:
        GeometryError: If the array shape does not match the grid.
    """

    grid: GridSpec
    data: FloatArray

    def __post_init__(self) -> None:
        """Reject an array that does not fit its grid."""
        if self.data.shape != self.grid.shape:
            msg = "raster array does not match its grid"
            raise GeometryError(msg, {"array": self.data.shape, "grid": self.grid.shape})

    @property
    def valid(self) -> NDArray[np.bool_]:
        """Mask of cells that carry a value."""
        return ~np.isnan(self.data)

    def with_data(self, data: FloatArray) -> Raster:
        """A new raster on the same grid — the way every derived surface is built."""
        return Raster(self.grid, np.asarray(data, dtype=np.float64))
