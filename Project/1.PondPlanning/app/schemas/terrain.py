"""Terrain layer contracts (FR2 and the derived surfaces)."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import GeoJSONFeatureCollection, QuantityOut, ResultWarning

DerivedSurface = Literal["slope", "aspect", "curvature", "twi", "hillshade", "flow_accumulation"]


class LayerDescriptor(BaseModel):
    """Everything the map client needs to add one layer and label it honestly."""

    layer_id: str
    kind: Literal["raster", "vector"]
    title: str
    tile_url_template: str
    legend_url: str | None = None
    units: str | None = None
    value_range: list[float] | None = Field(default=None, description="[min, max] for the legend")
    source: str = Field(description="What this layer was derived from")


class TerrainLayers(BaseModel):
    """The full toggleable layer set for a village — FR8's six overlays live here."""

    village_id: UUID
    layers: list[LayerDescriptor]


class DEMAsset(BaseModel):
    """Provenance of the elevation model every terrain number rests on.

    Exposed as an endpoint rather than buried in a log because the honesty of
    every downstream figure depends on it: a 1 m contour interval interpolated
    from a 30 m source is interpolated precision, not measured accuracy.
    """

    village_id: UUID
    source: str
    native_resolution: QuantityOut
    working_resolution: QuantityOut
    vertical_accuracy_relative: QuantityOut
    vertical_accuracy_absolute: QuantityOut
    crs: str
    acquired: str | None = None
    attribution: list[str]
    warnings: list[ResultWarning] = Field(default_factory=list)


class ContourResponse(BaseModel):
    """FR2: contours generated from the DEM pipeline at a requested interval."""

    village_id: UUID
    interval: QuantityOut
    levels: int = Field(description="Number of distinct elevation levels returned")
    vertices_before_simplification: int
    vertices_after_simplification: int
    simplification_tolerance: QuantityOut
    geojson: GeoJSONFeatureCollection
    warnings: list[ResultWarning] = Field(default_factory=list)


class StreamNetwork(BaseModel):
    """Extracted drainage network, with the threshold that produced it.

    ``accumulation_threshold`` is surfaced because it is the one knob that
    visibly changes the answer: too high and tributaries vanish, too low and the
    hillsides fill with spurious channels.
    """

    village_id: UUID
    accumulation_threshold: QuantityOut
    total_length: QuantityOut
    strahler_max_order: int
    geojson: GeoJSONFeatureCollection
    warnings: list[ResultWarning] = Field(default_factory=list)


class DerivedSurfaceResponse(BaseModel):
    """Slope, aspect, curvature, TWI, hillshade or flow accumulation as a layer."""

    village_id: UUID
    surface: DerivedSurface
    algorithm: str = Field(description="e.g. 'Horn (1981) 3x3 finite difference'")
    statistics: dict[str, QuantityOut]
    layer: LayerDescriptor
    warnings: list[ResultWarning] = Field(default_factory=list)


class TerrainPreparationResult(BaseModel):
    """P1 job result: a working DEM, its provenance, and the layers it yields.

    This is what ``POST /analyzeContour`` produces until the catchment engine
    lands in P2, at which point :class:`~app.schemas.analysis.ContourAnalysisResult`
    embeds it. ``catchment`` is present and ``null`` so a client can see the
    shape of what is coming rather than discover a missing key.
    """

    village_id: UUID
    village_name: str
    provider: str
    elevation_source: str
    contour_count: int
    contour_interval: QuantityOut
    grid_resolution: QuantityOut
    utm_epsg: int
    bounds: list[float] = Field(description="[min_lon, min_lat, max_lon, max_lat]")
    elevation: dict[str, QuantityOut]
    mean_slope: QuantityOut
    dem: DEMAsset
    layers: list[LayerDescriptor]
    boundary_geojson: dict[str, Any]
    catchment: None = Field(default=None, description="Arrives in P2")
    warnings: list[ResultWarning] = Field(default_factory=list)
