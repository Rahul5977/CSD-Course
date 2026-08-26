"""Terrain product catalogue: which rasters the pipeline writes and how each is styled.

One table, used by the workflow (to write) and by the layer builder (to
describe), so a surface cannot exist in storage without a layer and vice
versa. Colour maps and value ranges are TiTiler query parameters.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RasterProduct:
    """A stored raster surface and its rendering recipe."""

    key: str  # object-store suffix, e.g. "slope.tif"
    layer_id: str
    title: str
    units: str | None
    colormap: str | None
    algorithm: str
    dtype: str = "float32"
    nodata: float | None = -9999.0
    fixed_range: tuple[float, float] | None = None  # else p2..p98 from statistics
    default_visible: bool = False


PRODUCTS: dict[str, RasterProduct] = {
    "dem": RasterProduct(
        "dem.tif", "dem", "Elevation", "m", "terrain",
        "Delaunay TIN of the uploaded contours",
    ),
    "filled": RasterProduct(
        "filled.tif", "filled", "Conditioned elevation", "m", "terrain",
        "Priority-Flood + epsilon (Barnes et al. 2014)",
    ),
    "fill_depth": RasterProduct(
        "fill_depth.tif", "fill_depth", "Sink fill depth", "m", "magma",
        "filled - original; the cells the conditioning changed",
    ),
    "hillshade": RasterProduct(
        "hillshade.tif", "hillshade", "Hillshade", None, None,
        "Horn (1981) slope/aspect, azimuth 315, altitude 45", dtype="uint8", nodata=0,
        default_visible=True,
    ),
    "slope": RasterProduct(
        "slope.tif", "slope", "Slope", "deg", "viridis", "Horn (1981) 3x3", fixed_range=(0, 10),
    ),
    "aspect": RasterProduct(
        "aspect.tif", "aspect", "Aspect", "deg", "hsv", "Horn (1981) 3x3", fixed_range=(0, 360),
    ),
    "curvature": RasterProduct(
        "curvature.tif", "curvature", "Profile curvature", "1/100 m", "rdbu",
        "Zevenbergen & Thorne (1987)", fixed_range=(-1, 1),
    ),
    "plan_curvature": RasterProduct(
        "plan_curvature.tif", "plan_curvature", "Plan curvature", "1/100 m", "rdbu",
        "Zevenbergen & Thorne (1987)", fixed_range=(-1, 1),
    ),
    "twi": RasterProduct(
        "twi.tif", "twi", "Topographic wetness index", None, "blues",
        "ln(a / tan beta), Beven & Kirkby (1979)",
    ),
    "flow_accumulation": RasterProduct(
        "flow_accumulation.tif", "flow_accumulation", "Flow accumulation (log10 cells)",
        "log10 cells", "magma", "D8 (O'Callaghan & Mark 1984), descending-elevation pass",
    ),
}  # fmt: skip

#: Vector products written as GeoJSON to the store.
STREAMS_KEY = "streams.json"
SITING_KEY = "siting.json"
