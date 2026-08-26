"""Sentinel-2 L2A via the Earth Search STAC API and public COGs on AWS.

Search: ``POST/GET https://earth-search.aws.element84.com/v1/search`` for
``sentinel-2-l2a`` items over a bbox and date range, sorted by cloud cover.
Read: windowed reads of the ``green`` (B03) and ``nir`` (B08) COGs — a few
hundred kilobytes for a village — with the scene classification (``scl``)
to mask clouds. Median composite over the clearest scenes in a season.
Standard library for the search, rasterio for the bytes.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.domain.errors import UpstreamUnavailableError

logger = logging.getLogger(__name__)

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"
#: SCL classes treated as unusable: 0 nodata, 1 saturated, 3 cloud shadow,
#: 8/9 cloud medium/high, 10 thin cirrus, 11 snow.
SCL_BAD = (0, 1, 3, 8, 9, 10, 11)


@dataclass(frozen=True, slots=True)
class BandWindow:
    """Green, NIR and validity for one scene over the bbox, on the scene's grid."""

    green: NDArray[np.float64]
    nir: NDArray[np.float64]
    valid: NDArray[np.bool_]
    transform: tuple[float, float, float, float, float, float]
    epsg: int
    scene_id: str
    cloud_cover: float
    date: str


@dataclass(frozen=True, slots=True)
class SeasonComposite:
    """Median NDWI inputs over the season's scenes."""

    green: NDArray[np.float64]
    nir: NDArray[np.float64]
    transform: tuple[float, float, float, float, float, float]
    epsg: int
    scenes: list[str]
    label: str


def search_scenes(
    bounds_lonlat: tuple[float, float, float, float],
    start: str,
    end: str,
    *,
    max_cloud: float = 20.0,
    limit: int = 40,
    timeout_s: float = 60.0,
) -> list[dict[str, Any]]:
    """STAC items over the bbox in ``[start, end]`` with cloud cover under ``max_cloud``."""
    w, s, e, n = bounds_lonlat
    query = urllib.parse.urlencode(
        {
            "collections": "sentinel-2-l2a",
            "bbox": f"{w},{s},{e},{n}",
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
            "limit": limit,
        }
    )
    request = urllib.request.Request(
        f"{STAC_SEARCH}?{query}",
        headers={"User-Agent": "pond-planner/0.1", "Accept": "application/geo+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            doc = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        msg = f"STAC search unreachable: {exc}"
        raise UpstreamUnavailableError(msg, {"bbox": list(bounds_lonlat)}) from exc
    items = [
        f
        for f in doc.get("features", [])
        if float(f["properties"].get("eo:cloud_cover", 100.0)) <= max_cloud
    ]
    items.sort(key=lambda f: float(f["properties"].get("eo:cloud_cover", 100.0)))
    return items


def read_scene(
    item: dict[str, Any], bounds_lonlat: tuple[float, float, float, float]
) -> BandWindow:
    """Windowed read of green, NIR and SCL for one STAC item."""
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    assets = item["assets"]
    props = item["properties"]
    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_TIMEOUT": "60",
    }
    try:
        with rasterio.Env(**env):
            with rasterio.open(assets["green"]["href"]) as g:
                w, s, e, n = transform_bounds("EPSG:4326", g.crs, *bounds_lonlat)
                win = from_bounds(w, s, e, n, g.transform)
                green = g.read(1, window=win).astype(np.float64)
                transform = g.window_transform(win)
                epsg = int(g.crs.to_epsg())
                shape = green.shape
            with rasterio.open(assets["nir"]["href"]) as nb:
                nir = nb.read(
                    1, window=from_bounds(w, s, e, n, nb.transform), out_shape=shape
                ).astype(np.float64)
            with rasterio.open(assets["scl"]["href"]) as sb:
                scl = sb.read(1, window=from_bounds(w, s, e, n, sb.transform), out_shape=shape)
    except Exception as exc:
        msg = f"Sentinel-2 COG read failed: {exc}"
        raise UpstreamUnavailableError(msg, {"scene": item.get("id")}) from exc
    valid = ~np.isin(scl, SCL_BAD) & (green > 0) & (nir > 0)
    return BandWindow(
        green=green,
        nir=nir,
        valid=valid,
        transform=(transform.a, transform.b, transform.c, transform.d, transform.e, transform.f),
        epsg=epsg,
        scene_id=str(item.get("id")),
        cloud_cover=float(props.get("eo:cloud_cover", 0.0)),
        date=str(props.get("datetime", ""))[:10],
    )


def season_composite(
    bounds_lonlat: tuple[float, float, float, float],
    start: str,
    end: str,
    label: str,
    *,
    max_scenes: int = 3,
) -> SeasonComposite:
    """Median of the clearest ``max_scenes`` scenes' green and NIR, cloud-masked."""
    items = search_scenes(bounds_lonlat, start, end)
    if not items:
        msg = f"no clear Sentinel-2 scenes for {label} ({start}..{end})"
        raise UpstreamUnavailableError(msg, {"season": label})
    windows: list[BandWindow] = []
    for item in items[: max_scenes * 2]:
        try:
            windows.append(read_scene(item, bounds_lonlat))
        except UpstreamUnavailableError as exc:
            logger.warning("scene skipped", extra={"reason": exc.message})
        if len(windows) >= max_scenes:
            break
    if not windows:
        msg = f"no readable Sentinel-2 scene for {label}"
        raise UpstreamUnavailableError(msg, {"season": label})
    shape = windows[0].green.shape
    windows = [w for w in windows if w.green.shape == shape]
    green = np.stack([np.where(w.valid, w.green, np.nan) for w in windows])
    nir = np.stack([np.where(w.valid, w.nir, np.nan) for w in windows])
    with np.errstate(all="ignore"):
        g_med = np.nanmedian(green, axis=0)
        n_med = np.nanmedian(nir, axis=0)
    return SeasonComposite(
        green=np.asarray(g_med),
        nir=np.asarray(n_med),
        transform=windows[0].transform,
        epsg=windows[0].epsg,
        scenes=[w.scene_id for w in windows],
        label=label,
    )
