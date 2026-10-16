# ADR 0022 — OpenTelemetry: traces, metrics and logs through one collector

**Status:** Accepted · 2026-10-16 · Phase P10 (Phase 3 add-on)

## Context

The Phase 3 add-on (`docs/assignment/Phase3.txt`, *ADD_ON*) requires OpenTelemetry in this
project: instrument the components, capture logs, traces and metrics, export them to
backends that can show them, and explain what they reveal.

P6 already had observability (ADR 0019), but each signal stood alone. Prometheus
counters were scraped from `/metrics`, JSON logs carried an `X-Request-ID`, and there
were no traces. A job's path from the POST, through Redis, into a worker could only be
followed by grepping for an id. Nothing showed where the time inside the pipeline went.

## Decision

1. **SDK in every Python process.** `app/core/telemetry.py` installs a `TracerProvider`,
   a `MeterProvider` and a `LoggerProvider`, all exporting **OTLP/HTTP** to one
   collector. Each process is identified by its `Resource`: `service.name` is
   `pond-api`, `pond-worker-interactive` or `pond-worker-heavy`; it also carries
   `service.version` and `deployment.environment`. The SDK is off unless
   `POND_OTEL_ENABLED=true`. When off, the API's no-op providers make every call free.
2. **Auto-instrumentation for the libraries already in use.**
   - **FastAPI:** a server span plus HTTP metrics for each route; probes are excluded.
   - **SQLAlchemy:** one span per SQL statement.
   - **Redis:** one span per command.
   - **Celery:** publish and run spans. The trace context travels in the message
     headers, so the worker's spans join the API's trace.
   - **urllib:** spans for Open-Meteo, NASA POWER, WorldCover, SoilGrids and Nominatim.
3. **A span per algorithm stage, without touching the engines.** Every workflow already
   writes `jobs.update(stage=…)`. `StageObservingJobs` is a **Decorator** over the job
   repository: each new stage ends the previous stage span and starts the next one as a
   child of the job span. Each stage span is made *current*, so the SQL and HTTP spans
   of that stage nest under it. The engines and workflows import nothing new, and
   `tests/test_layering.py` still passes. A Jaeger waterfall therefore reads as the
   algorithm: *parsing → TIN → Priority-Flood → D8 → streams → siting → catchment*.
4. **Domain metrics** sit alongside the HTTP and DB ones:
   - `pond.job.duration` and `pond.job.stage.duration` (s)
   - `pond.jobs.active`
   - `pond.catchment.area` (ha) and `pond.design.storage` (m³)

   Results are also span attributes (`pond.catchment.area_ha`), so a slow trace shows
   what it computed.
5. **Logs over OTLP, correlated.** An OTLP `LoggingHandler` sits on the root logger. It
   is re-attached after `configure_logging` and after Celery resets the logging setup.
   Every record carries the trace and span id of the code that emitted it. The JSON
   stdout formatter adds the same `trace_id`/`span_id`.
6. **One collector, three backends** (`infra/otel/collector.yaml`). The pipeline is
   `memory_limiter → batch`, and the collector routes each signal:

   | Signal | Backend | How |
   |---|---|---|
   | Traces | **Jaeger** | OTLP gRPC |
   | Metrics | **Prometheus** | scraped from the collector's `:8889` |
   | Logs | **Loki** | native `/otlp` endpoint |
   | All three | `debug` exporter | one summary line per batch |

   **Grafana** shows all three. Jaeger traces link to their Loki logs, and Loki lines
   link back to their trace by `trace_id`.
7. **Context through the thread pool.** `ThreadJobRunner` submits each job inside
   `contextvars.copy_context()`. On the lab deployment, the job span is then the child
   of the `POST` that created it, exactly as through Celery.

## Alternatives rejected

- **Zero-code agent (`opentelemetry-instrument`).** It cannot see pipeline stages, and
  the setup would be hidden from the reader. Explicit setup is about 80 lines that can
  be explained line by line in the viva.
- **Exporting straight from the app to Jaeger/Loki.** It couples the code to the
  backends. With a collector, swapping Jaeger for Tempo, or adding sampling, is a
  config change only.
- **Manual spans inside the engines.** They would put a framework into the pure core
  and break the layering rule. The repository decorator gets the same spans from data
  the workflows already write.
- **Replacing `prometheus_client`.** The P6 dashboard, backpressure and alerts are
  built on it. OTel metrics run alongside it under their own `pond.*` names, so the
  two can be compared.
- **Grafana `otel-lgtm` all-in-one image.** It's convenient, but it hides the collector
  pipeline, which is the part this assignment asks students to understand.

## Consequences

- The Compose file grows by three services (`otel-collector`, `jaeger`, `loki`), to 14.
- The BatchSpanProcessor exports in the background, so request latency is unaffected.
  The cost is a few seconds' delay before a trace appears in Jaeger.
- Lab VMs: telemetry stays off by default, because the VMs cannot run the backends
  (no Docker). The thread-runner context propagation is in place for when they can.
- `tests/test_telemetry.py` asserts, with in-memory exporters, that one upload is one
  trace: from `POST /api/v1/analyzeContour` through `job contour_analysis` to
  `stage: filling sinks (Priority-Flood)`.
