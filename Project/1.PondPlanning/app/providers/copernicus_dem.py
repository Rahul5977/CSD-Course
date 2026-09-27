"""Copernicus DEM GLO-30 — windowed reads of the public COG tiles, warped to UTM.

The tiles are published as Cloud-Optimised GeoTIFFs on the AWS Open Data
registry (``s3://copernicus-dem-30m``, no key, no registration), one per
1°x1° cell, named by the cell's south-west corner. A COG carries an internal
tile index, so rasterio reads only the byte ranges under the requested window
over HTTP (GDAL ``/vsicurl/``) — a village-sized box is a few hundred kB, not
the 25 MB tile.

Algorithm: for every 1° tile the box touches, read the window (plus a
two-cell margin so bilinear sampling has neighbours at the edge) and
**reproject** it onto the destination UTM grid with bilinear resampling. Tiles
are mosaicked by filling only still-empty cells, so a box that straddles a
degree line comes out seamless. A missing tile (open sea) leaves NaN, and an
all-NaN result is reported rather than silently analysed.

A small in-process LRU cache keyed on the rounded box makes a repeated
selection (the demo, a second user on the same village) free.
"""

from __future__ import annotations

import math
import time
from functools import lru_cache

import numpy as np
import rasterio
from rasterio.errors import RasterioIOError
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds

from app.domain.errors import UpstreamUnavailableError, ValidationError
from app.domain.geo import GridSpec
from app.domain.raster import Raster

DEFAULT_BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"


def tile_name(lat_floor: int, lon_floor: int) -> str:
    """Official tile id for the 1° cell whose south-west corner is (lat, lon)."""
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def tiles_for(bounds: tuple[float, float, float, float]) -> list[str]:
    """Every tile id a lon/lat box touches (usually one, at most four at village scale)."""
    west, south, east, north = bounds
    return [
        tile_name(lat, lon)
        for lat in range(math.floor(south), math.floor(north) + 1)
        for lon in range(math.floor(west), math.floor(east) + 1)
    ]


def tile_url(base_url: str, name: str) -> str:
    """Location of a tile under ``base_url`` — an https root or a local directory."""
    path = f"{base_url.rstrip('/')}/{name}/{name}.tif"
    return f"/vsicurl/{path}" if path.startswith(("http://", "https://")) else path


def wbm_url(base_url: str, name: str) -> str:
    """The tile's Water Body Mask (0 land, 1 ocean, 2 lake, 3 river), same grid as the DEM."""
    stem = name.removesuffix("_DEM")
    path = f"{base_url.rstrip('/')}/{name}/AUXFILES/{stem}_WBM.tif"
    return f"/vsicurl/{path}" if path.startswith(("http://", "https://")) else path


def read_glo30(
    bounds: tuple[float, float, float, float], grid: GridSpec, base_url: str = DEFAULT_BASE_URL
) -> Raster:
    """Mosaic and warp the GLO-30 tiles under ``bounds`` onto ``grid`` (cached).

    Raises:
        UpstreamUnavailableError: If no tile could be read at all.
        ValidationError: If the box has no land elevation (open sea).
    """
    try:
        data = _warp_cached(grid, base_url, "dem")
    except TransientReadError as exc:
        msg = "Copernicus GLO-30 tiles could not be reached (network); retry in a moment"
        raise UpstreamUnavailableError(msg, {"bounds": list(bounds), "error": str(exc)}) from exc
    if data is None:
        msg = "Copernicus GLO-30 tiles could not be read for this area"
        raise UpstreamUnavailableError(msg, {"bounds": list(bounds)})
    if np.isnan(data).all():
        msg = "the selected area has no land elevation data (open water or outside coverage)"
        raise ValidationError(msg, {"bounds": list(bounds)})
    return Raster(grid, data.copy())


def read_glo30_water(grid: GridSpec, base_url: str = DEFAULT_BASE_URL) -> np.ndarray | None:
    """Boolean mask of mapped water (lake or river) on ``grid``, or None if unavailable.

    Why it is needed: GLO-30 *flattens* water surfaces during editing. On a
    flattened river D8 splits the flow into parallel lines, so no single cell
    accumulates enough to be recognised as a river and siting would put a
    pond in it. The mask restores what the elevations hide.
    """
    try:
        data = _warp_cached(grid, base_url, "wbm")
    except TransientReadError:
        return None
    if data is None:
        return None
    return (data >= 1.5) & (data <= 3.5)  # nearest-resampled classes 2 (lake) and 3 (river)


@lru_cache(maxsize=64)
def _warp_cached(grid: GridSpec, base_url: str, product: str) -> np.ndarray | None:
    """Warp one product of every tile under the grid onto it; None if no tile was readable."""
    # Read for the *grid's* footprint: the UTM grid is the envelope of the
    # projected box, so its corners reach slightly beyond the requested box.
    west, south, east, north = transform_bounds(
        f"EPSG:{grid.epsg}",
        "EPSG:4326",
        grid.x_min,
        grid.y_max - grid.rows * grid.cell_size,
        grid.x_min + grid.cols * grid.cell_size,
        grid.y_max,
        densify_pts=21,
    )
    dst = np.full((grid.rows, grid.cols), np.nan, dtype=np.float64)
    url = tile_url if product == "dem" else wbm_url
    resampling = Resampling.bilinear if product == "dem" else Resampling.nearest
    read_any = False
    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "1",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    }
    transient: list[str] = []
    with rasterio.Env(**env):
        for name in tiles_for((west, south, east, north)):
            tile = _read_tile(url(base_url, name), (west, south, east, north), grid, resampling)
            if isinstance(tile, str):
                transient.append(f"{name}: {tile}")
                continue
            if tile is None:
                continue  # open sea has no tile; a missing aux file is not fatal
            fill = np.isnan(dst) & ~np.isnan(tile)
            dst[fill] = tile[fill]
            read_any = True
    if not read_any and transient:
        # Raised, not returned: lru_cache must not remember a network blip.
        raise TransientReadError("; ".join(transient)[:300])
    return dst if read_any else None


class TransientReadError(Exception):
    """Every tile read failed on the network (DNS, connect, timeout) — worth retrying later."""


_TRANSIENT = ("resolve host", "couldn't connect", "could not connect", "timed out", "timeout")


def _read_tile(
    path: str,
    bounds: tuple[float, float, float, float],
    grid: GridSpec,
    resampling: Resampling,
    attempts: int = 3,
) -> np.ndarray | str | None:
    """Warp one tile onto ``grid``.

    Returns the array; ``None`` when the tile does not exist (open sea, no aux
    file); or the error text when the network failed on every attempt. GDAL's
    libcurl does its own DNS, and the lab VMs' resolvers drop ~40 % of lookups,
    so a transient failure is retried with a short backoff; a 404 is not.
    """
    west, south, east, north = bounds
    dst_transform = Affine(grid.cell_size, 0, grid.x_min, 0, -grid.cell_size, grid.y_max)
    error = ""
    for attempt in range(attempts):
        try:
            with rasterio.open(path) as src:
                # Two source cells of margin, at the tile's own resolution.
                mx, my = 2 * abs(src.res[0]), 2 * abs(src.res[1])
                window = (
                    from_bounds(west - mx, south - my, east + mx, north + my, src.transform)
                    .round_offsets(op="floor")
                    .round_lengths(op="ceil")
                )
                window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
                block = src.read(1, window=window, out_dtype="float64")
                if src.nodata is not None:
                    block[block == src.nodata] = np.nan
                tile = np.full((grid.rows, grid.cols), np.nan, dtype=np.float64)
                reproject(
                    source=block,
                    destination=tile,
                    src_transform=src.window_transform(window),
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=f"EPSG:{grid.epsg}",
                    src_nodata=np.nan,
                    dst_nodata=np.nan,
                    resampling=resampling,
                )
                return tile
        except rasterio.errors.WindowError:
            return None
        except RasterioIOError as exc:
            error = str(exc)
            if not any(marker in error.lower() for marker in _TRANSIENT):
                return None
            time.sleep(1.0 * (attempt + 1))
    return error or "unreadable"
