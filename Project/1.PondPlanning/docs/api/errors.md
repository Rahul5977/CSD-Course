# Error catalogue

Every error this API returns uses one shape — [RFC 9457 problem details](https://www.rfc-editor.org/rfc/rfc9457) —
so a client parses failures the same way everywhere:

```json
{
  "type": "https://github.com/Rahul5977/AI-BasedPondAnalysis/blob/main/docs/api/errors.md#elevation_not_found",
  "title": "No elevation could be read from the uploaded contour map",
  "status": 422,
  "code": "elevation_not_found",
  "detail": { "strategies_tried": ["z_coordinate", "extended_data", "placemark_name"] },
  "instance": "/api/v1/analyzeContour"
}
```

**Branch on `code`, not on `status`.** The status tells you the class of failure;
the code tells you which one. Two different `422`s need different handling.

This page is the human copy. The machine copy is generated from the same table
the handlers use, at `GET /api/v1/meta/errors`, so the two cannot drift.

| `code` | HTTP | Meaning | What the caller should do |
|---|---|---|---|
| `not_found` | 404 | The referenced village, job or recommendation does not exist. | Check the id. |
| `validation_error` | 400 | Well-formed request, unusable values. | Fix the values; the `detail` names them. |
| `request_validation_error` | 422 | The body or query parameters failed schema validation. | `detail.errors` is Pydantic's field-level report. |
| `geometry_error` | 422 | Geometry is invalid, empty, or self-intersecting. | Repair the geometry before resubmitting. |
| `crs_error` | 422 | An array or geometry reached a computation in the wrong CRS. | Should never reach a client — report it as a bug. |
| `unsupported_input` | 422 | The file parsed, but this system cannot analyse it. | See `detail` for what was expected. |
| `elevation_not_found` | 422 | No elevation could be read from an uploaded contour map. | See below — this one has a story. |
| `job_failed` | 409 | The job terminated without producing a result. | Read `detail.stage`, then retry or adjust the request. |
| `upstream_unavailable` | 503 | A DEM, rainfall or imagery provider could not be reached. | Retry with backoff. Cached results may still be served with a staleness marker. |
| `not_implemented_yet` | 501 | The route's contract is fixed but its engine is not built. | Expected during P0-P4. See `GET /api/v1/meta/implementation-status`. |

## `elevation_not_found` — why this fails instead of guessing

An uploaded contour map can carry elevation in three places, and this system
tries them in order: the Z coordinate, then an `ExtendedData` field whose name
matches `elev|elevation|contour|level|height`, then the placemark `<name>`.

If all three fail, the request is rejected. It would be easy to fall back to
"the first numeric field in `ExtendedData`" — and on the provided sample map that
field is `ID`, a sequential row number from 0 to 1354. That fallback produces a
complete, plausible-looking terrain model built from row numbers, and nothing
downstream would flag it.

A loud failure is the only safe behaviour. `detail.strategies_tried` reports
which strategies ran, and successful requests report the strategy that worked in
`elevation_source`, so any result can be audited after the fact.

## Fixture responses

While an engine is unimplemented, its route returns a realistic fixture rather
than an error, so the frontend can be built against the final contract. Those
responses are always labelled:

- header `X-Fixture-Data: true`
- a `fixture_data` entry in the payload's `warnings[]`, at `critical` severity

`GET /api/v1/meta/implementation-status` lists what is real and what is not.
