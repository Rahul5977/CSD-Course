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


def read_cog(payload: bytes) -> Raster:
    """Load a single-band GeoTIFF back into a :class:`Raster` (nodata → NaN)."""
    from app.domain.geo import GridSpec

    with MemoryFile(payload) as memory, memory.open() as dataset:
        transform = dataset.transform
        epsg = dataset.crs.to_epsg()
        grid = GridSpec(
            epsg=int(epsg),
            x_min=float(transform.c),
            y_max=float(transform.f),
            cell_size=float(transform.a),
            rows=dataset.height,
            cols=dataset.width,
        )
        data = dataset.read(1).astype(np.float64)
        if dataset.nodata is not None:
            data = np.where(data == dataset.nodata, np.nan, data)
        return Raster(grid, data)


def mask_to_polygon_lonlat(mask: np.ndarray, raster: Raster) -> dict[str, object]:
    """Vectorise a boolean mask into one (Multi)Polygon GeoJSON geometry in EPSG:4326.

    Uses GDAL's polygonizer, dissolves the pieces, simplifies at half a cell,
    and reprojects — the same chain a GIS would run.
    """
    from pyproj import Transformer
    from rasterio.features import shapes
    from shapely.geometry import mapping, shape
    from shapely.ops import transform as shp_transform
    from shapely.ops import unary_union

    a, b, c, d, e, f = raster.grid.affine
    transform = Affine(a, b, c, d, e, f)
    pieces = [
        shape(geometry)
        for geometry, value in shapes(mask.astype("uint8"), mask=mask, transform=transform)
        if value == 1
    ]
    if not pieces:
        return {"type": "Polygon", "coordinates": []}
    merged = unary_union(pieces).simplify(raster.grid.cell_size / 2, preserve_topology=True)
    to_lonlat = Transformer.from_crs(f"EPSG:{raster.grid.epsg}", "EPSG:4326", always_xy=True)
    return dict(mapping(shp_transform(to_lonlat.transform, merged)))


def polygon_perimeter_m(mask: np.ndarray, raster: Raster) -> float:
    """Perimeter of the dissolved mask polygon, in metres."""
    from rasterio.features import shapes
    from shapely.geometry import shape
    from shapely.ops import unary_union

    a, b, c, d, e, f = raster.grid.affine
    pieces = [
        shape(g)
        for g, v in shapes(mask.astype("uint8"), mask=mask, transform=Affine(a, b, c, d, e, f))
        if v == 1
    ]
    return float(unary_union(pieces).length) if pieces else 0.0


__all__ = [
    "mask_to_polygon_lonlat",
    "polygon_perimeter_m",
    "rasterio",
    "read_cog",
    "read_raster_bounds_lonlat",
    "write_cog",
]
