# Demonstration script — 7 minutes

Pre-flight (5 min before): `make up && make seed`; open http://localhost:3000, http://localhost:8000/docs
and http://localhost:3001 in three tabs; keep `docs/media/chaos-test.gif` open as the backup.
Never depend on a live external API during the demo: the rainfall record is cached, the land
cover and water mask are stored per village by `make seed`'s follow-up suitability run.

| # | Time | Show | Say |
|---|---|---|---|
| 1 | 0:30 | Landing page at `/` — scroll past the hero to *Nothing is a black box*; click *Open the planner* | "The system takes only a contour map. Everything you will see is derived from that file — the UTM zone, the grid, the source accuracy, the pour point. Every algorithm on this page is named and cited." |
| 2 | 0:45 | Upload `contours_1m.kml`; progress stages; village appears as *Khapri*; contours + streams draw | "Parse → TIN → Priority-Flood → D8. The streams are the modelled network at 5 ha; compare with the river in the imagery. The village name came from reverse-geocoding the centroid." |
| 3 | 1:00 | Suggested sites panel; hover the criterion bars; *How sites are ranked* | "Four terrain criteria — an upstream-area plateau, a slope plateau, wetness, impoundment efficiency — AHP-weighted, consistency ratio 0.004. Not a black box: every site shows its scores." |
| 4 | 0:45 | Click site #1 → catchment polygon, snapped outlet, snap distance | "38 ha, ±26 %. Validated against pysheds within 2–3 % on the main outlets; the sensitivity plot in the report shows why snapping matters." |
| 5 | 1:15 | Rainfall card → *Design a pond at the outlet* → dimensions, EAV curve, methods table, reliability | "45 years of ERA5-Land; the 75 % dependable year is 1 168 mm. Three runoff methods disagree by 188 % — that range is information. The depth is chosen by cost; it fills in 25 of 25 years." |
| 6 | 0:45 | *Assess land & rank sites* (pre-run) → eligible patches, constraint list, ownership unknown | "Seven named constraints; ownership is 'unknown' because no cadastral layer was supplied — never assumed government." |
| 7 | 0:45 | Log in as planner → save → submit; log in as officer → approve → audit trail → *Export PDF* | "State machine plus roles; every move is an append-only audit row. The PDF attaches to an MGNREGA proposal." |
| 8 | 0:45 | `docker stop pond-planner-api-1`; reload; offline badge, results still there; `docker start …` | "Village internet is 2G and intermittent. Cached results with a staleness badge." |
| 9 | 0:30 | Grafana dashboard; Swagger | "Two worker bulkheads, Prometheus metrics, 40 documented operations with an error catalogue." |

Questions to expect: why D8 (ADR 0009) · why the area plateau (ADR 0014) · why SCS-CN daily
(ADR 0010) · why not ML (ADR 0017) · what the ±20 % means (DEM is 30 m-derived) · why no
GRASS (ADR 0015) · why FastAPI/PostGIS over Flask/Mongo (ADR 0005, 0006).

## OpenTelemetry segment (Phase 3 add-on) — 3 minutes

Pre-flight: `make up && make seed`; in the planner open Khapri, click site #1 → *Design a pond*.
Tabs: Jaeger http://localhost:16686 · Grafana http://localhost:3001/d/pond-otel · Grafana Explore (Loki).

| # | Show | Say |
|---|---|---|
| 1 | `infra/otel/collector.yaml` (or Fig. 1 of the report) | "Every process pushes OTLP to one collector; the collector routes traces to Jaeger, metrics to Prometheus, logs to Loki. The code knows only the collector." |
| 2 | Jaeger → service `pond-api`, operation `POST /api/v1/analyzeContour` → open the trace | "One upload, one trace across two containers: the POST, its SQL and Redis calls, `apply_async` onto the queue, then the heavy worker picks it up — the context crossed Redis in the message headers." |
| 3 | Collapse-all, expand to the stage spans | "One span per algorithm stage — Priority-Flood 31 ms, D8 8 ms, ranking 180 ms. The engines don't import OpenTelemetry: a decorator on the job repository turns the stage updates the UI already uses into spans." |
| 4 | Point at *reading the water body mask* | "The finding: the hydrology is milliseconds; 52–70 % of a cold job is one network read of the GLO-30 water mask. Re-run the same map: that stage drops to ~6 ms (in-process cache). Optimise the read — a cache shared by all workers — not the algorithm." |
| 5 | Jaeger → operation `POST /api/v1/analysis/pond-design` → red ❗ span | "This design said 'confidence low'. The trace says why: the SoilGrids call failed DNS after 4 s; the span holds the exception." |
| 6 | Grafana Explore → Loki `{service_name="pond-worker-interactive"} |= "soil"` → expand → *Open trace in Jaeger* | "The warning log carries the same trace id — from a log line to its trace in one click." |
| 7 | Grafana dashboard *Pond — OpenTelemetry* | "Metrics are the trend: stage time histograms, job durations, HTTP p95 by route, and domain metrics — mean catchment area, designed storage." |

Questions to expect: span vs trace vs context · why a collector · how context crosses Celery
(W3C `traceparent` in headers) · why batch processors · what the Resource is · why the engines
don't import OTel (layering, ADR 0001) · sampling in production (tail sampling in the collector).
