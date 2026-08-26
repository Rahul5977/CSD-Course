# Error catalogue

Every error leaves the API as an RFC 9457 problem document with a stable `code`.
Generated from `GET /api/v1/meta/errors` (the same table the handlers use), so it cannot drift.

| code | HTTP | exception | meaning |
|---|---|---|---|
| `crs_error` | 422 | `CRSError` | An array or geometry reached a computation in the wrong CRS. |
| `elevation_not_found` | 422 | `ElevationNotFoundError` | No elevation could be read from an uploaded contour map. |
| `forbidden` | 403 | `AuthorizationError` | The caller is known but lacks the role. |
| `geometry_error` | 422 | `GeometryError` | Geometry is invalid, empty, or in an unusable coordinate system. |
| `illegal_transition` | 409 | `IllegalTransitionError` | The requested status change is not allowed from the current state. |
| `job_failed` | 409 | `JobFailedError` | An asynchronous job terminated without producing a result. |
| `not_found` | 404 | `NotFoundError` | A referenced entity does not exist. |
| `not_implemented_yet` | 501 | `NotImplementedYetError` | The route exists and its contract is fixed, but the engine is not built. |
| `queue_saturated` | 429 | `BackpressureError` | The target queue is saturated; retry later. |
| `unauthenticated` | 401 | `AuthenticationError` | Missing, expired or invalid credentials. |
| `unsupported_input` | 422 | `UnsupportedInputError` | The uploaded file parsed, but this system cannot analyse it. |
| `upstream_unavailable` | 503 | `UpstreamUnavailableError` | An external provider (DEM, rainfall, imagery) could not be reached. |
| `validation_error` | 400 | `ValidationError` | The request was well-formed but the values are unusable. |
| `request_validation_error` | 422 | `RequestValidationError` | The request body or parameters failed validation (FastAPI's default, reshaped) |

Example:

```json
{
  "type": "https://github.com/Rahul5977/AI-BasedPondAnalysis/blob/main/docs/api/errors.md#not_found",
  "title": "no such village",
  "status": 404,
  "code": "not_found",
  "detail": {
    "village_id": "3f2a9c1e-5b7d-4e8a-9c1f-2d6b8e4a7c93"
  },
  "instance": "/api/v1/villages/3f2a9c1e-5b7d-4e8a-9c1f-2d6b8e4a7c93/summary"
}
```
