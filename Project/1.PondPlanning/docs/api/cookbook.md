# API cookbook

Base URL: `http://localhost:8000/api/v1` (or `http://localhost:3000/api/v1` through nginx,
which is what the browser uses). Interactive documentation: `/docs` (Swagger UI), `/redoc`;
the machine-readable contract is `docs/api/openapi.json` (`make openapi` regenerates it).
Every trimmed response below is a real one captured from the running stack on the sample
map and stored under `docs/api/samples/`.

Conventions:

- **Long analyses are jobs.** `POST` returns `202` with a `job_id` and `poll_url`; poll
  `GET /jobs/{id}` (or open the WebSocket `/jobs/{id}/ws`), then read the result from the
  documented result route. Send an `Idempotency-Key` header so a retry returns the same job.
- **Every number is a `QuantityOut`**: `{value, unit, uncertainty_pct, low, high, method, display}`.
- **Errors are RFC 9457 problem documents** with a stable `code` — see `errors.md`.
- Mutating recommendation routes need a bearer token (`/auth/token`).

## 1. Analyse a contour map (the Phase 2 route)

```bash
curl -s -F "file=@data/samples/contours_1m.kml" -H "Idempotency-Key: $(uuidgen)" \
  http://localhost:8000/api/v1/analyzeContour
```
→ `202` — `samples/job_accepted.json`
```json
{"job_id": "…", "status": "queued", "poll_url": "/api/v1/jobs/…", "estimated_seconds": 35}
```

Poll until `succeeded` (≈ 5–10 s on the sample):
```bash
curl -s http://localhost:8000/api/v1/jobs/$JOB
```
→ `samples/job_status.json` (`stage` names the pipeline step; `progress` is a percentage).

Result — suggested pond location, its rationale, its catchment, five ranked candidates and
the siting method, plus the terrain block (DEM provenance, layers, elevation statistics):
```bash
curl -s http://localhost:8000/api/v1/analysis/results/contour/$JOB | jq '{village_name, suggested_pond_location, location_rationale, catchment: .catchment.area, candidates: [.candidate_sites[] | {rank, score: .score.value, upstream_area: .upstream_area.display}], cr: .siting.weights}'
```

Rules the parser applies (ADR 0011): only `LineString` placemarks are contours; elevation is
read from the Z coordinate, then a whitelisted `ExtendedData` field (`elev|contour|level|height|altitude|z`),
then the placemark `<name>`; numeric `ID`-like fields are never accepted; `.kmz` is unwrapped;
a `<Folder>` root is fine. The UTM zone comes from the file's own centroid.

## 2. Villages, summary, layers

```bash
curl -s http://localhost:8000/api/v1/villages                       # samples/villages.json
curl -s http://localhost:8000/api/v1/villages/$VID/summary           # samples/village_summary.json (FR1)
curl -s http://localhost:8000/api/v1/villages/$VID/imagery           # basemap descriptor
curl -s http://localhost:8000/api/v1/villages/$VID/siting            # samples/siting.json
curl -s http://localhost:8000/api/v1/terrain/$VID/layers             # samples/terrain_layers.json (FR8 layer list)
curl -s http://localhost:8000/api/v1/terrain/$VID/dem                # DEM provenance and accuracy
curl -s "http://localhost:8000/api/v1/terrain/$VID/contours?interval=5"   # FR2, GeoJSON lines with elevation
curl -s http://localhost:8000/api/v1/terrain/$VID/streams            # D8 network, Strahler order
curl -s http://localhost:8000/api/v1/terrain/$VID/derived/twi        # slope|aspect|curvature|twi|hillshade|flow_accumulation
```
Raster layers are served by TiTiler from Cloud-Optimised GeoTIFFs; each descriptor's
`tile_url_template` is a `/tiles/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?url=…&rescale=…&colormap_name=…` URL.

## 3. Catchment for a clicked point (FR4)

```bash
curl -s -X POST -H "Content-Type: application/json" -H "Idempotency-Key: $(uuidgen)" \
  -d '{"village_id": "'$VID'", "pour_point": {"lon": 81.2842, "lat": 21.2622}}' \
  http://localhost:8000/api/v1/analysis/catchment
curl -s http://localhost:8000/api/v1/analysis/results/catchment/$JOB   # samples/catchment_result.json
```
The point is snapped to the nearest channel cell draining ≥ 2 ha within 150 m; `snap_distance`
says how far. A catchment touching the map edge carries the `catchment_truncated` warning.
`snap_to_drainage: false` disables snapping; `snap_radius` overrides the radius (metres).

## 4. Rainfall (FR5)

```bash
curl -s "http://localhost:8000/api/v1/rainfall/statistics?lon=81.297&lat=21.2517&years=30"   # samples/rainfall_statistics.json
curl -s "http://localhost:8000/api/v1/rainfall/series?lon=81.297&lat=21.2517&start=2019-06-01&end=2019-09-30"
```
`dependable_75` is the design figure (Weibull plotting position). `fallback_used` is `none`,
`cache` (live API unreachable, cached record served) or `secondary_provider` (NASA POWER).

## 5. Runoff (FR6) and pond design (FR7)

```bash
# runoff on an existing catchment job
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"village_id": "'$VID'", "catchment_job_id": "'$CATCHMENT_JOB'", "years": 20}' \
  http://localhost:8000/api/v1/analysis/runoff
curl -s http://localhost:8000/api/v1/analysis/results/runoff/$JOB      # samples/runoff_result.json

# the full design at a point (does its own catchment, rainfall, runoff)
curl -s -X POST -H "Content-Type: application/json" -H "Idempotency-Key: $(uuidgen)" \
  -d '{"village_id": "'$VID'", "pour_point": {"lon": 81.2842, "lat": 21.2622}, "target_reliability": 0.75}' \
  http://localhost:8000/api/v1/analysis/pond-design
curl -s http://localhost:8000/api/v1/analysis/results/pond-design/$JOB  # samples/pond_design_result.json
```
Optional `curve_number` overrides the derived CN; `max_depth` caps the search. The design
payload carries `dimensions`, `gross/live/dead_storage`, the `eav_curve`, `reliability`,
`bill_of_quantities`, `confidence` + `confidence_rationale`, and warnings that spell out the
water balance, the natural impoundment and the curve-number basis.

## 6. Available land and suitability (FR3)

```bash
curl -s -X POST -H "Content-Type: application/json" -d '{"village_id": "'$VID'", "top_n": 8}' \
  http://localhost:8000/api/v1/analysis/suitability        # 60–90 s: reads Sentinel-2 live
curl -s http://localhost:8000/api/v1/analysis/results/suitability/$JOB
curl -s http://localhost:8000/api/v1/villages/$VID/available-land       # samples/available_land.json
```
`weights` may be supplied (normalised); otherwise the declared Saaty matrix is used and the
`consistency_ratio` is returned (must be < 0.10). Each site lists every criterion's raw
value, membership, weight and contribution.

## 7. Authentication and the recommendation lifecycle

```bash
TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
  -d '{"username": "planner", "password": "planner-demo"}' http://localhost:8000/api/v1/auth/token | jq -r .access_token)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"design_job_id": "'$DESIGN_JOB'"}' http://localhost:8000/api/v1/recommendations    # samples/recommendation.json
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status": "submitted", "reason": "ready for review"}' http://localhost:8000/api/v1/recommendations/$REC/status
# officer approves; a viewer gets 403, draft→approved gets 409 illegal_transition
curl -s http://localhost:8000/api/v1/recommendations/$REC/audit
curl -s -X POST "http://localhost:8000/api/v1/recommendations/$REC/exports?export_format=pdf"
curl -sO http://localhost:8000/api/v1/exports/$EXPORT.pdf
```
Roles: `viewer` < `planner` (save, submit) < `officer` (approve, reject). Every accepted
transition writes an outbox event drained into the append-only `audit_log` (`samples/error_409_illegal_transition.json`).

## 8. Operations

```bash
curl -s http://localhost:8000/health · /ready · /metrics
curl -s http://localhost:8000/api/v1/meta/implementation-status   # what is real (everything) and what is a fixture
curl -s http://localhost:8000/api/v1/meta/errors                  # the error catalogue
```
Backpressure: when a queue holds more than `POND_MAX_QUEUE_DEPTH` jobs, analysis POSTs answer
`429 queue_saturated` with a `Retry-After` header.
