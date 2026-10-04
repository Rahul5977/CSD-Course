"""Wire types shared by every resource.

Kept in one module so that a client — or the AI design tool building the frontend —
learns these four shapes once and then recognises them everywhere.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.units import Quantity, Unit


class QuantityOut(BaseModel):
    """A number with its unit, uncertainty band and provenance.

    The wire counterpart of :class:`app.domain.units.Quantity`. ``display`` is
    included deliberately: it removes any chance of the frontend rendering
    "18950" because someone forgot to append the unit, and it is what appears in
    report screenshots.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "value": 18950.0,
                "unit": "m3",
                "uncertainty_pct": 20.0,
                "low": 15160.0,
                "high": 22740.0,
                "method": "EAV curve integrated over the filled depression",
                "display": "18,950.00 m³ (±20 %)",
            }
        }
    )

    value: float
    unit: Unit
    uncertainty_pct: float | None = Field(
        default=None,
        description="Symmetric relative uncertainty in percent. null means exact by construction.",
    )
    low: float | None = Field(default=None, description="Lower bound of the uncertainty band")
    high: float | None = Field(default=None, description="Upper bound of the uncertainty band")
    method: str | None = Field(default=None, description="How the value was derived")
    display: str | None = Field(default=None, description="Preformatted for direct rendering")

    @classmethod
    def from_domain(cls, quantity: Quantity) -> QuantityOut:
        """Project a domain :class:`Quantity` onto the wire."""
        return cls(
            value=quantity.value,
            unit=quantity.unit,
            uncertainty_pct=quantity.uncertainty_pct,
            low=quantity.low,
            high=quantity.high,
            method=quantity.method,
            display=str(quantity),
        )


class ProblemDetail(BaseModel):
    """RFC 9457 problem details — the single error shape for every route.

    One documented error envelope, rather than FastAPI's default bare
    ``{"detail": ...}``, is what makes an error catalogue possible: ``code`` is
    stable and machine-readable, ``status`` matches the HTTP status, and
    ``detail`` carries structured context such as which field failed.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "https://github.com/Rahul5977/AI-BasedPondAnalysis/docs/errors#elevation_not_found",
                "title": "No elevation could be read from the uploaded contour map",
                "status": 422,
                "code": "elevation_not_found",
                "detail": {"strategies_tried": ["z_coordinate", "extended_data", "placemark_name"]},
                "instance": "/api/v1/analyzeContour",
            }
        }
    )

    type: str = Field(description="URI identifying the error class")
    title: str = Field(description="Short human-readable summary")
    status: int = Field(
        description="HTTP status code, repeated for clients that only read the body"
    )
    code: str = Field(description="Stable machine-readable identifier; see the error catalogue")
    detail: dict[str, Any] = Field(default_factory=dict, description="Structured context")
    instance: str | None = Field(default=None, description="The request path that failed")


class ResultWarning(BaseModel):
    """A caveat attached to an otherwise successful result.

    Warnings are how this system avoids presenting a number more confidently than
    it deserves — "the source DEM is 30 m, so relief below ~5 m is interpolated,
    not measured" belongs next to the storage estimate, not buried in a report.
    """

    code: str
    message: str
    severity: Literal["info", "caution", "critical"] = "caution"


class JobAccepted(BaseModel):
    """``202`` response for every long-running analysis.

    Terrain analysis takes tens of seconds. Rather than hold a connection open
    and hope no proxy times it out, every analysis route returns this immediately
    and the client polls ``poll_url``.
    """

    job_id: UUID
    status: Literal["queued"] = "queued"
    poll_url: str = Field(description="GET this until status is succeeded or failed")
    estimated_seconds: int = Field(description="Rough expectation, for the progress UI")


class JobStatus(BaseModel):
    """Progress of an asynchronous job."""

    job_id: UUID
    kind: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress: Annotated[int, Field(ge=0, le=100)]
    stage: str | None = Field(default=None, description="Current pipeline stage, for the UI")
    created_at: datetime
    finished_at: datetime | None = None
    error: ProblemDetail | None = None
    result_url: str | None = None


class Page[T](BaseModel):
    """Cursor-free pagination envelope. Adequate at village and district scale."""

    items: list[T]
    total: int
    limit: int
    offset: int


class GeoJSONFeature(BaseModel):
    """A GeoJSON Feature, loosely typed.

    Geometry is not modelled field-by-field on purpose: the map client consumes
    it directly, and a hand-written GeoJSON type is a large surface that adds no
    safety the client actually uses. Geometry validity is enforced in PostGIS and
    in the engines, where it matters.
    """

    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)


class GeoJSONFeatureCollection(BaseModel):
    """A GeoJSON FeatureCollection, always in EPSG:4326 on the wire.

    Every computation happens in the UTM zone derived from the data's own
    centroid; 4326 is the interchange format only. ``crs`` is stated explicitly
    so no consumer has to assume.
    """

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]
    crs: str = Field(default="EPSG:4326", description="Always EPSG:4326 on the wire")
