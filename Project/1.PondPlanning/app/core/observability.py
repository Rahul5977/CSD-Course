"""Request correlation and Prometheus metrics (P6).

**Correlation.** Every request gets an ``X-Request-ID`` (taken from the
caller if present, else generated) held in a ``ContextVar``; the JSON log
formatter adds it to every line, and Celery tasks set the same variable to
their job id, so one grep follows a request into the worker.

**Metrics.** Prometheus counters/histograms for HTTP requests, job durations,
provider errors and cache hits, plus a queue-depth gauge the worker fills
from Redis. Exposed at ``/metrics`` (API) and on port 9100 (worker).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

HTTP_REQUESTS = Counter("pond_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram(
    "pond_http_request_seconds", "HTTP request latency", ["route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)  # fmt: skip
JOB_DURATION = Histogram(
    "pond_job_seconds", "Analysis job duration", ["kind", "status"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)  # fmt: skip
PROVIDER_ERRORS = Counter("pond_provider_errors_total", "External provider failures", ["provider"])
CACHE_EVENTS = Counter("pond_cache_events_total", "Cache hits/misses", ["cache", "event"])
QUEUE_DEPTH = Gauge("pond_queue_depth", "Celery queue depth", ["queue"])
RATE_LIMITED = Counter("pond_backpressure_total", "Requests refused with 429", ["queue"])


def install(app: FastAPI) -> None:
    """Add the correlation + metrics middleware and the ``/metrics`` route."""

    @app.middleware("http")
    async def _observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        route = getattr(request.scope.get("route"), "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        HTTP_LATENCY.labels(route).observe(time.perf_counter() - started)
        response.headers["X-Request-ID"] = rid
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def observe_job(kind: str, status: str, seconds: float) -> None:
    """Record a finished job."""
    JOB_DURATION.labels(kind, status).observe(seconds)
