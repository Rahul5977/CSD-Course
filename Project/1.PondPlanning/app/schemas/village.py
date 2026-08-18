"""Village, imagery and available-land contracts (FR1, FR3)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import GeoJSONFeatureCollection, QuantityOut, ResultWarning


class VillageCreate(BaseModel):
    """Register a village by name and boundary."""

    name: Annotated[str, Field(min_length=1, max_length=128)]
    state_code: str | None = Field(default=None, max_length=8)
    district: str | None = None
    boundary: dict[str, Any] = Field(description="GeoJSON MultiPolygon or Polygon, EPSG:4326")


class VillageOut(BaseModel):
    """A registered village."""

    id: UUID
    name: str
    state_code: str | None
    district: str | None
    centroid: list[float] = Field(description="[lon, lat] in EPSG:4326")
    utm_epsg: int = Field(
        description=(
            "Projected CRS used for every area and distance computation, derived at "
            "runtime from this village's own centroid — never configured, never hard-coded."
        )
    )
    area: QuantityOut
    created_at: datetime


class ElevationSummary(BaseModel):
    """Elevation statistics over the village boundary."""

    minimum: QuantityOut
    maximum: QuantityOut
    mean: QuantityOut
    relief: QuantityOut = Field(description="maximum - minimum")


class VillageSummary(BaseModel):
    """FR1: the headline card shown when a village is selected.

    Every field is a :class:`QuantityOut`, so the panel cannot render a bare
    number even by accident.
    """

    village: VillageOut
    elevation: ElevationSummary
    mean_slope: QuantityOut
    dem_source: str = Field(description="Provider and native resolution, for attribution")
    dem_vertical_accuracy: QuantityOut
    warnings: list[ResultWarning] = Field(default_factory=list)


class ImageryLayer(BaseModel):
    """FR1: a satellite basemap clipped to the village boundary."""

    layer_id: str
    provider: str
    tile_url_template: str = Field(description="XYZ template for the map client")
    attribution: str
    captured: str | None = Field(default=None, description="Acquisition date or range, if known")
    max_zoom: int


class LandParcel(BaseModel):
    """FR3: one polygon of land judged available for excavation."""

    parcel_id: str
    ownership_class: Literal["government", "community", "private", "unknown"] = Field(
        description=(
            "Ownership *class*, never an owner's name — personal data under the "
            "DPDP Act 2023. See ADR 0012."
        )
    )
    area: QuantityOut
    mean_slope: QuantityOut
    lulc_class: str
    excluded_by: list[str] = Field(
        default_factory=list, description="Constraints that rejected this parcel, if any"
    )
    eligible: bool


class AvailableLandResponse(BaseModel):
    """FR3: eligible excavation land, with the constraint set that produced it."""

    village_id: UUID
    constraints_applied: list[str]
    total_eligible_area: QuantityOut
    parcels: list[LandParcel]
    geojson: GeoJSONFeatureCollection
    warnings: list[ResultWarning] = Field(default_factory=list)
