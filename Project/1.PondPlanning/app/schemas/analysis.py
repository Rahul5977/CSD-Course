"""Analysis contracts: catchment, runoff, pond design, suitability (FR4, FR6, FR7, FR3).

These are the payloads the whole project builds towards. They are fixed here, in
P0, precisely so the frontend can be built against them while the engines behind
them are still being written.
"""

from __future__ import annotations

from typing import Annotated, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import GeoJSONFeatureCollection, QuantityOut, ResultWarning
from app.schemas.terrain import TerrainPreparationResult

RunoffMethod = Literal["scs_cn", "rational", "empirical_strange"]


class PourPoint(BaseModel):
    """The location a catchment is delineated for."""

    lon: Annotated[float, Field(ge=-180, le=180)]
    lat: Annotated[float, Field(ge=-90, le=90)]


class CatchmentRequest(BaseModel):
    """FR4: delineate the upstream contributing area of a clicked point."""

    village_id: UUID
    pour_point: PourPoint
    snap_to_drainage: bool = Field(
        default=True,
        description=(
            "Move the pour point onto the nearest modelled channel before tracing "
            "upstream. Without it, a click one cell off the channel returns a "
            "hillslope catchment orders of magnitude too small."
        ),
    )
    snap_radius: float | None = Field(
        default=None, description="Metres. Defaults to the configured radius."
    )


class CatchmentResult(BaseModel):
    """FR4: the delineated catchment, and enough context to trust it."""

    village_id: UUID
    requested_point: PourPoint
    snapped_point: PourPoint
    snap_distance: QuantityOut = Field(
        description="How far the pour point moved. Surfaced in the UI — a large "
        "snap distance is the signal that the result should be questioned."
    )
    area: QuantityOut
    perimeter: QuantityOut
    longest_flow_path: QuantityOut
    mean_slope: QuantityOut
    relief: QuantityOut
    outlet_elevation: QuantityOut
    flow_routing: str = Field(description="e.g. 'D8 (O'Callaghan & Mark 1984)'")
    cell_size: QuantityOut
    geojson: GeoJSONFeatureCollection
    warnings: list[ResultWarning] = Field(default_factory=list)


class RunoffRequest(BaseModel):
    """FR6: convert rainfall over a catchment into a runoff volume."""

    village_id: UUID
    catchment_job_id: UUID = Field(description="The catchment this runoff is computed on")
    methods: list[RunoffMethod] = Field(
        default_factory=lambda: list(get_args(RunoffMethod)),
        description="Runs every requested method so the answer is a range, not a point.",
    )
    curve_number: float | None = Field(
        default=None, ge=30, le=100, description="Override the derived CN"
    )
    years: int = Field(default=20, ge=5, le=50)


class RunoffMethodResult(BaseModel):
    """One method's answer, with the assumptions that produced it."""

    method: RunoffMethod
    annual_runoff_volume: QuantityOut
    runoff_coefficient: QuantityOut
    parameters: dict[str, QuantityOut]
    reference: str = Field(description="Citation for the method")


class RunoffResult(BaseModel):
    """FR6: three methods, reported as a range.

    Three methods rather than one because they disagree, and the disagreement is
    information. A single number here would be false precision.
    """

    village_id: UUID
    catchment_area: QuantityOut
    results: list[RunoffMethodResult]
    recommended: RunoffMethodResult
    spread_pct: QuantityOut = Field(description="Disagreement between the methods")
    warnings: list[ResultWarning] = Field(default_factory=list)


class PondDesignRequest(BaseModel):
    """FR7: size a pond for a location."""

    village_id: UUID
    pour_point: PourPoint
    target_reliability: float = Field(
        default=0.75,
        ge=0.5,
        le=0.95,
        description="Fraction of years the pond should fill. 0.75 is the "
        "dependability standard used in Indian minor-irrigation practice.",
    )
    max_depth: float | None = Field(default=None, description="Metres. Site or safety limit.")


class EAVPoint(BaseModel):
    """One row of the elevation-area-volume curve."""

    elevation: QuantityOut
    surface_area: QuantityOut
    cumulative_volume: QuantityOut


class PondDimensions(BaseModel):
    """The excavation, in numbers a contractor can act on."""

    depth: QuantityOut
    top_length: QuantityOut
    top_width: QuantityOut
    bottom_length: QuantityOut
    bottom_width: QuantityOut
    side_slope: QuantityOut = Field(description="Horizontal:vertical, as a ratio")
    freeboard: QuantityOut


class BillOfQuantities(BaseModel):
    """Excavation quantities and an indicative cost."""

    excavation_volume: QuantityOut
    embankment_volume: QuantityOut
    indicative_cost: QuantityOut
    cost_basis: str = Field(description="Schedule of rates used, and its year")


class PondDesignResult(BaseModel):
    """FR7 — the full payload, and the single most important contract here.

    Deliberately assembled from every upstream stage rather than returned as a
    bare storage figure: catchment, rainfall, runoff, geometry, reliability,
    quantities, caveats and an overall confidence label. The confidence label is
    what stops a 30 m-DEM result being read as a survey.
    """

    village_id: UUID
    catchment: CatchmentResult
    rainfall_summary: dict[str, QuantityOut]
    runoff: RunoffResult
    dimensions: PondDimensions
    gross_storage: QuantityOut
    live_storage: QuantityOut
    dead_storage: QuantityOut
    eav_curve: list[EAVPoint]
    reliability: QuantityOut = Field(description="Fraction of years the pond fills")
    bill_of_quantities: BillOfQuantities
    confidence: Literal["low", "moderate", "high"]
    confidence_rationale: str
    warnings: list[ResultWarning] = Field(default_factory=list)


class SuitabilityRequest(BaseModel):
    """FR3/P4: rank candidate pond sites across a village."""

    village_id: UUID
    top_n: int = Field(default=10, ge=1, le=100)
    weights: dict[str, float] | None = Field(
        default=None, description="AHP criterion weights. Derived if omitted."
    )


class CriterionScore(BaseModel):
    """One criterion's contribution to a site's score."""

    criterion: str
    raw_value: QuantityOut
    normalised_score: QuantityOut
    weight: QuantityOut
    contribution: QuantityOut


class SuitableSite(BaseModel):
    """One ranked candidate location."""

    rank: int
    location: PourPoint
    total_score: QuantityOut
    criteria: list[CriterionScore]
    catchment_area: QuantityOut
    estimated_storage: QuantityOut


class SuitabilityResult(BaseModel):
    """FR3/P4: ranked sites, with the AHP matrix that ranked them.

    ``consistency_ratio`` is returned, not just computed. AHP weights are only
    meaningful when CR < 0.10; publishing the value is what makes the ranking
    checkable rather than asserted.
    """

    village_id: UUID
    sites: list[SuitableSite]
    weights: dict[str, float]
    consistency_ratio: float = Field(description="AHP CR; must be < 0.10 to be valid")
    consistency_acceptable: bool
    warnings: list[ResultWarning] = Field(default_factory=list)


class SiteCandidateOut(BaseModel):
    """One ranked pond location from the terrain-only siting engine (P2).

    ``criteria`` carries the normalised score of every criterion so the ranking
    is checkable: an evaluator can see *why* rank 1 beat rank 2.
    """

    rank: int
    location: PourPoint
    score: QuantityOut
    upstream_area: QuantityOut
    local_slope: QuantityOut
    wetness_index: QuantityOut
    impoundment_volume: QuantityOut = Field(
        description="Water held behind a nominal rise at this point, from the DEM"
    )
    impoundment_efficiency: QuantityOut = Field(
        description="Impounded volume per unit footprint — the mean pool depth"
    )
    criteria: dict[str, float]


class SitingMethod(BaseModel):
    """The rules that produced the ranking, returned so they can be defended."""

    weights: dict[str, float]
    nominal_rise: QuantityOut
    max_slope: QuantityOut
    suppression_radius: QuantityOut
    stream_threshold: QuantityOut
    upstream_area_bounds_ha: list[float] = Field(
        description="[too small, ideal from, ideal to, too large] — the upstream-area plateau"
    )
    candidates_considered: int
    river_cells_excluded: int = Field(
        0,
        description="Drainage cells excluded as an existing river: channel cells at or "
        "beyond the plateau's upper bound, plus every cell inside the flood-belt buffer "
        "around channels beyond the ideal band",
    )
    river_buffer: QuantityOut | None = Field(
        None,
        description="Flood-belt setback: no candidate within this distance of a channel "
        "whose upstream area exceeds the plateau's ideal band — a bund there would face "
        "the large channel's spates",
    )
    max_upstream_area_ha: float = Field(
        0.0,
        description="Largest upstream area draining through any channel cell, in hectares — "
        "the size of the biggest watercourse in the map",
    )
    description: str


class ContourAnalysisResult(BaseModel):
    """The Phase 2 submission payload: pond location + catchment from an uploaded contour map.

    Everything here is derived from the upload. The UTM zone comes from the
    file's own centroid, the grid resolution from its own mean contour spacing,
    the source accuracy from its own metadata and the pour point from its own
    modelled drainage — nothing is configured per map, which is exactly what
    the assignment's anti-hard-coding rule requires.
    """

    source_file: str
    village_id: UUID
    village_name: str
    contour_count: int
    elevation_source: Literal["z_coordinate", "extended_data", "placemark_name"] = Field(
        description="Which parsing strategy succeeded, so the result is auditable"
    )
    elevation_range: dict[str, QuantityOut]
    contour_interval: QuantityOut
    bounds: list[float] = Field(description="[min_lon, min_lat, max_lon, max_lat]")
    utm_epsg: int = Field(description="Derived from the uploaded file's centroid")
    grid_resolution: QuantityOut = Field(
        description="Derived from mean contour spacing, floored at the source resolution"
    )
    suggested_pond_location: PourPoint
    location_rationale: str
    catchment: CatchmentResult | None = Field(
        None,
        description="Catchment of the suggested location. Null only when the map has no "
        "modelled drainage at all (too small or too flat) — the warnings say so",
    )
    candidate_sites: list[SiteCandidateOut]
    siting: SitingMethod
    terrain: TerrainPreparationResult
    warnings: list[ResultWarning] = Field(default_factory=list)
