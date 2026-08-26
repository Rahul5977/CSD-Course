"""Raster serialisation — the only module that knows GDAL exists.

Writes Cloud-Optimised GeoTIFFs: internally tiled, overviews built, so TiTiler
can serve any zoom level by reading a few byte ranges rather than the file.
"""

from __future__ import annotations

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine

from app.domain.raster import Raster


def write_cog(raster: Raster, *, dtype: str = "float32", nodata: float | None = None) -> bytes:
    """Serialise a raster as a COG and return the bytes.

    Args:
        raster: The grid and data. ``NaN`` cells become ``nodata`` when one is given.
        dtype: ``float32`` for elevations and continuous surfaces, ``uint8`` for
            hillshade and other pre-scaled imagery.
        nodata: Value written for missing cells. For ``uint8`` hillshade this is
            0, which the engine reserves for exactly this purpose.
    """
    data = raster.data
    if nodata is not None:
        data = np.where(np.isnan(data), nodata, data)
    array = data.astype(dtype)
    a, b, c, d, e, f = raster.grid.affine
    profile = {
        "driver": "COG",
        "height": raster.grid.rows,
        "width": raster.grid.cols,
        "count": 1,
        "dtype": dtype,
        "crs": f"EPSG:{raster.grid.epsg}",
        "transform": Affine(a, b, c, d, e, f),
        "compress": "deflate",
        "blocksize": 256,
        "overview_resampling": "average",
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with MemoryFile() as memory:
        with memory.open(**profile) as dataset:
            dataset.write(array, 1)
        return bytes(memory.read())


def read_raster_bounds_lonlat(payload: bytes) -> tuple[float, float, float, float]:
    """Bounds of a GeoTIFF in EPSG:4326, for the map client's fit-to-extent."""
    from rasterio.warp import transform_bounds

    with MemoryFile(payload) as memory, memory.open() as dataset:
        west, south, east, north = transform_bounds(dataset.crs, "EPSG:4326", *dataset.bounds)
        return (float(west), float(south), float(east), float(north))


__all__ = ["rasterio", "read_raster_bounds_lonlat", "write_cog"]
