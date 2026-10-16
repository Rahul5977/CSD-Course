# DAY_13 — 2026-10-16
**Phase:** P10 (Phase 3 add-on: OpenTelemetry) · **Gate:** G10

## What worked
- OTel SDK in the API and both Celery workers; OTLP/HTTP → collector → Jaeger / Prometheus / Loki → Grafana.
- One upload = one trace across two containers (context in Celery headers), with a span per algorithm stage — produced by a decorator over the job repository, so the engines import nothing new.
- `tests/test_telemetry.py`: 5 tests with in-memory exporters; `make check` 226 passed.
- Real findings from the data: the water-body-mask read is 52–70 % of a contour job (Priority-Flood 31 ms, D8 8 ms); a pond design's "confidence low" traced to a SoilGrids DNS failure (`URLError [Errno -5]`, 4.0 s), with the WARN log carrying the same trace id.

## What broke
- `make seed` sent the old upload field `file` (renamed `contour_map` on 2026-09-03) → fixed.
- Docker Hub pulls reset by the campus network → retried.
- ~85 ASGI `http receive` spans per 6 MB upload buried the waterfall → `exclude_spans`.
- nginx kept the old API address after rebuilding only the API → *Bad Gateway* → README troubleshooting row.

## Screenshot
`docs/figures/otel/03-jaeger-algorithm-stages.jpg`, `06-grafana-otel-metrics.jpg`, `07-loki-log-with-trace-id.jpg`

## Decisions made
Collector over direct export · stage spans from a repository decorator · OTel metrics beside prometheus_client · stable HTTP semconv · context copied into pool threads · off by default, on in compose (all in the PROGRESS decision log, ADR 0022).

## Tomorrow's three tasks
1. Rehearse the 3-minute OTel segment in `docs/DEMO.md` against a fresh `make up`.
2. Submit `docs/report/OpenTelemetry_Report.pdf`.
3. Optional: cache the GLO-30 water-body mask per tile (the bottleneck the trace found).
