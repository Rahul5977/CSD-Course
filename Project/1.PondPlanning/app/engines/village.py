"""Village-level derivations: geometry facts and the FR1 summary card."""

from __future__ import annotations

from typing import Any

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

from app.domain.geo import utm_epsg_for
from app.domain.units import Quantity, Unit
from app.repositories.records import DEMAssetRecord, VillageRecord
from app.schemas.common import QuantityOut, ResultWarning
from app.schemas.village import ElevationSummary, ImageryLayer, VillageOut, VillageSummary

ESRI_WORLD_IMAGERY = ImageryLayer(
    layer_id="esri-world-imagery",
    provider="Esri World Imagery",
    tile_url_template=(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    ),
    attribution="Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    captured=None,
    max_zoom=19,
)


def boundary_facts(boundary: dict[str, Any]) -> tuple[tuple[float, float], int, float]:
    """``(centroid lon/lat, utm_epsg, area_m2)`` for a GeoJSON geometry in EPSG:4326.

    The UTM zone is derived from the centroid, and the area is measured in that
    zone — never in degrees.
    """
    geometry = shape(boundary)
    centroid = geometry.centroid
    epsg = utm_epsg_for(centroid.x, centroid.y)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True).transform
    area = float(shapely_transform(to_utm, geometry).area)
    return (float(centroid.x), float(centroid.y)), epsg, area


def describe_village(record: VillageRecord) -> VillageOut:
    """Project a stored village onto the wire, with derived CRS and area."""
    (lon, lat), epsg, area_m2 = boundary_facts(record.boundary)
    return VillageOut(
        id=record.id,
        name=record.name,
        state_code=record.state_code,
        district=record.district,
        centroid=[lon, lat],
        utm_epsg=epsg,
        area=QuantityOut.from_domain(
            Quantity(area_m2 / 1e4, Unit.HECTARE, None, f"boundary polygon area in EPSG:{epsg}")
        ),
        boundary=record.boundary,
        created_at=record.created_at,
    )


def imagery_layer() -> ImageryLayer:
    """FR1 basemap descriptor. The map client clips it to the boundary."""
    return ESRI_WORLD_IMAGERY


def village_summary(record: VillageRecord, asset: DEMAssetRecord) -> VillageSummary:
    """FR1 headline card: area, elevation range, mean slope, DEM provenance."""
    stats = asset.statistics
    rel = asset.vertical_accuracy_relative_m
    method = f"{asset.source}, gridded at {asset.working_resolution_m:g} m"

    def elev(value: float, how: str = method) -> QuantityOut:
        pct = 100.0 * rel / value if value else None
        return QuantityOut.from_domain(Quantity(value, Unit.METRE, pct, how))

    relief = float(stats["relief"])
    relief_pct = 100.0 * (2**0.5) * rel / relief if relief else None
    warnings = [
        ResultWarning(
            code="boundary_is_upload_extent",
            message=(
                "The boundary is the extent drawn in the uploaded contour map, not an "
                "administrative village boundary."
            ),
            severity="info",
        )
    ]
    return VillageSummary(
        village=describe_village(record),
        elevation=ElevationSummary(
            minimum=elev(float(stats["min"])),
            maximum=elev(float(stats["max"])),
            mean=elev(float(stats["mean"]), "zonal mean over the grid"),
            relief=QuantityOut.from_domain(
                Quantity(relief, Unit.METRE, relief_pct, "maximum - minimum")
            ),
        ),
        mean_slope=QuantityOut.from_domain(
            Quantity(float(stats["mean_slope_deg"]), Unit.DEGREE, 15.0, "Horn (1981) 3x3, mean")
        ),
        dem_source=f"{asset.source} · working grid {asset.working_resolution_m:g} m",
        dem_vertical_accuracy=QuantityOut.from_domain(
            Quantity(rel, Unit.METRE, None, "relative, LE90")
        ),
        warnings=warnings,
    )
