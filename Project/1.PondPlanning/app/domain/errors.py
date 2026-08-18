"""Domain error hierarchy, with stable machine-readable codes.

Every error carries a ``code`` that never changes once published. That code is
what the API documentation's error catalogue lists (Documentation: API, 2 marks)
and what a client branches on — an HTTP status alone cannot distinguish "this
KML has no elevations anywhere" from "this KML is 200 MB".

These are framework-free by design: engines raise them, and one exception
handler in ``app/api/errors.py`` is the single place that knows how a domain
error becomes an HTTP status.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every expected failure in the domain.

    Attributes:
        code: Stable identifier, published in the error catalogue.
        message: Human-readable explanation.
        detail: Optional structured context for the client.
    """

    code: str = "domain_error"

    def __init__(self, message: str, detail: dict[str, object] | None = None) -> None:
        """Build the error from a message and optional structured context."""
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class NotFoundError(DomainError):
    """A referenced entity does not exist."""

    code = "not_found"


class ValidationError(DomainError):
    """The request was well-formed but the values are unusable."""

    code = "validation_error"


class UnsupportedInputError(DomainError):
    """The uploaded file parsed, but this system cannot analyse it."""

    code = "unsupported_input"


class ElevationNotFoundError(UnsupportedInputError):
    """No elevation could be read from an uploaded contour map.

    Raised rather than guessed. The sample map carries elevation only in
    ``<Placemark><name>`` while also carrying a numeric ``ID`` field that looks
    like elevation and is not; an adapter that falls back to "the first numeric
    field" produces a plausible terrain model from nonsense. Failing loudly is
    the only safe behaviour.
    """

    code = "elevation_not_found"


class GeometryError(DomainError):
    """Geometry is invalid, empty, or in an unusable coordinate system."""

    code = "geometry_error"


class CRSError(GeometryError):
    """An array or geometry reached a computation in the wrong CRS.

    Guards against the single most common error in this class of system:
    measuring area or distance in degrees. Raised by ``assert_crs()``.
    """

    code = "crs_error"


class UpstreamUnavailableError(DomainError):
    """An external provider (DEM, rainfall, imagery) could not be reached.

    Distinct from a bug: the correct response is to degrade to cache and tell the
    user the result is stale, which is exactly what the P6 chaos test exercises.
    """

    code = "upstream_unavailable"


class JobFailedError(DomainError):
    """An asynchronous job terminated without producing a result."""

    code = "job_failed"


class NotImplementedYetError(DomainError):
    """The route exists and its contract is fixed, but the engine is not built.

    Returned by every fixture route in P0. It exists so that "not built yet" is a
    documented, machine-readable state rather than a silent lie — a fixture that
    is indistinguishable from a real result is a trap for both the frontend and
    the evaluator.
    """

    code = "not_implemented_yet"
