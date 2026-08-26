"""Land-cover and soil providers for the curve-number engine.

**ESA WorldCover 2021 (10 m)** is read as a *window* straight from its
public Cloud-Optimised GeoTIFF on AWS — a few hundred kilobytes for a
village, no download, no key. **SoilGrids v2** (ISRIC) gives clay/sand at
0-30 cm for the hydrologic soil group. Both fall back to stated defaults
with a warning rather than failing the analysis: a curve number with a
caveat is more useful to a planner than no runoff figure at all.
"""

from __future__ import annotations

import json
import logging
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.errors import UpstreamUnavailableError
from app.domain.soil import HSG, hsg_from_texture

logger = logging.getLogger(__name__)

WORLDCOVER_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
)
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"


def worldcover_tile(lon: float, lat: float) -> str:
    """WorldCover tiles are 3° x 3°, named by their south-west corner."""
    lat0 = int(math.floor(lat / 3.0) * 3)
    lon0 = int(math.floor(lon / 3.0) * 3)
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    return f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}"


@dataclass(frozen=True, slots=True)
class LandCoverWindow:
    """A WorldCover window in EPSG:4326 with its affine transform."""

    codes: NDArray[np.uint8]
    transform: tuple[float, float, float, float, float, float]  # GDAL affine a..f
    source: str
    assumed: bool = False


class WorldCoverAdapter:
    """Windowed read of the ESA WorldCover COG for a lon/lat bounding box."""

    name = "esa_worldcover_2021"

    def __init__(self, timeout_s: float = 60.0) -> None:
        """GDAL's HTTP timeout is set through the environment inside :meth:`window`."""
        self._timeout = timeout_s

    def window(self, bounds_lonlat: tuple[float, float, float, float]) -> LandCoverWindow:
        """Read the classes covering ``bounds``. Raises ``UpstreamUnavailableError`` on failure."""
        import rasterio
        from rasterio.windows import from_bounds

        w, s, e, n = bounds_lonlat
        url = WORLDCOVER_URL.format(tile=worldcover_tile((w + e) / 2, (s + n) / 2))
        env = {
            "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
            "GDAL_HTTP_TIMEOUT": str(int(self._timeout)),
            "GDAL_HTTP_MAX_RETRY": "2",
        }
        try:
            with rasterio.Env(**env), rasterio.open(url) as dataset:
                win = from_bounds(w, s, e, n, dataset.transform)
                codes = dataset.read(1, window=win)
                transform = dataset.window_transform(win)
        except Exception as exc:
            msg = f"WorldCover unreachable: {exc}"
            raise UpstreamUnavailableError(msg, {"url": url}) from exc
        a, b, c, d, e_, f = (
            transform.a,
            transform.b,
            transform.c,
            transform.d,
            transform.e,
            transform.f,
        )
        return LandCoverWindow(
            codes=np.asarray(codes, dtype=np.uint8),
            transform=(a, b, c, d, e_, f),
            source=(
                "ESA WorldCover 2021 v200 (10 m), © ESA WorldCover project / "
                "Contains modified Copernicus Sentinel data (2021)"
            ),
        )


class ConstantLandCoverAdapter:
    """Fallback: one class everywhere (default cropland), flagged as assumed."""

    name = "assumed_landcover"

    def __init__(self, code: int = 40) -> None:
        """``code`` is the WorldCover class to assume."""
        self._code = code

    def window(self, bounds_lonlat: tuple[float, float, float, float]) -> LandCoverWindow:
        """A 1x1 window covering the bounds."""
        w, s, e, n = bounds_lonlat
        return LandCoverWindow(
            codes=np.array([[self._code]], dtype=np.uint8),
            transform=(e - w, 0.0, w, 0.0, -(n - s), n),
            source="assumed land cover (WorldCover unreachable)",
            assumed=True,
        )


@dataclass(frozen=True, slots=True)
class SoilTexture:
    """Topsoil texture and the group it implies."""

    clay_pct: float
    sand_pct: float
    hsg: HSG
    source: str
    assumed: bool = False


class SoilGridsAdapter:
    """ISRIC SoilGrids v2 point query, 0-30 cm mean clay and sand."""

    name = "soilgrids_v2"

    def __init__(self, timeout_s: float = 60.0) -> None:
        """SoilGrids is slow (tens of seconds); this runs in the worker, cached."""
        self._timeout = timeout_s

    def texture(self, lon: float, lat: float) -> SoilTexture:
        """Fetch clay/sand and classify. Raises ``UpstreamUnavailableError`` on failure."""
        query = urllib.parse.urlencode(
            [
                ("lon", f"{lon:.4f}"),
                ("lat", f"{lat:.4f}"),
                ("property", "clay"),
                ("property", "sand"),
                ("depth", "0-30cm"),
                ("value", "mean"),
            ]
        )
        request = urllib.request.Request(
            f"{SOILGRIDS_URL}?{query}",
            headers={"User-Agent": "pond-planner/0.1", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                doc = json.loads(response.read().decode("utf-8"))
            values: dict[str, float] = {}
            for layer in doc["properties"]["layers"]:
                depth = layer["depths"][0]
                # SoilGrids reports g/kg scaled x10; convert to per cent.
                values[layer["name"]] = float(depth["values"]["mean"]) / 10.0
            clay, sand = values["clay"], values["sand"]
        except Exception as exc:
            msg = f"SoilGrids unreachable or unparseable: {exc}"
            raise UpstreamUnavailableError(msg, {"lon": lon, "lat": lat}) from exc
        return SoilTexture(
            clay, sand, hsg_from_texture(clay, sand), "ISRIC SoilGrids v2.0 (0-30 cm mean)"
        )


class DefaultSoilAdapter:
    """Fallback: a stated default group (C — the loams of central India)."""

    name = "assumed_soil"

    def __init__(self, hsg: HSG = "C") -> None:
        """``hsg`` is the group to assume."""
        self._hsg = hsg

    def texture(self, lon: float, lat: float) -> SoilTexture:
        """A nominal C-group texture, flagged as assumed."""
        return SoilTexture(
            30.0, 40.0, self._hsg, "assumed hydrologic soil group (SoilGrids unreachable)", True
        )
