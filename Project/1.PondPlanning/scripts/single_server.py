"""One-port deployment: the API plus the built SPA from a single uvicorn process.

For hosts that cannot run Docker (the provided lab VMs are unprivileged
containers — no dockerd, no systemd). Pairs with the in-process adapters the
test suite already uses (``POND_PERSISTENCE=memory``, ``POND_JOB_RUNNER=inline``,
``POND_OBJECT_STORE=local``) so the entire analysis pipeline runs with no
external service. Raster tile layers need TiTiler and are absent in this mode;
every vector result (catchment, contours, streams, candidate sites) is served
by the API itself and renders normally.

Run:  uvicorn scripts.single_server:app --host 0.0.0.0 --port 8080

The FastAPI routes keep priority; the static mount catches everything else,
serving ``web/dist`` with ``index.html`` fallback for the SPA routes.
"""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from pathlib import Path
from typing import Any

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.main import app

DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

# The lab hosts advertise IPv6 routes that never connect, so every stdlib
# client burns its whole timeout on the AAAA record before trying IPv4 —
# which is why reverse geocoding fell back to a coordinate name there.
# Sorting IPv4 first is a deployment-scoped fix: app code stays untouched.
#
# Their resolvers (1.1.1.1, 8.8.8.8 over a lossy uplink) also fail ~40 % of
# lookups ("Temporary failure in name resolution", measured 2026-09-27), which
# stalled a runoff job for minutes on provider retries. So lookups are also
# retried quickly, cached for an hour, and served stale when the resolver is
# down — the provider hosts barely ever change address.
_getaddrinfo = socket.getaddrinfo
_DNS_TTL_S = 3600.0
_dns_cache: dict[tuple[Any, ...], tuple[float, Any]] = {}
_dns_lock = threading.Lock()


def _ipv4_first(*args: Any, **kwargs: Any) -> Any:
    key = (*args, *sorted(kwargs.items()))
    with _dns_lock:
        hit = _dns_cache.get(key)
    if hit is not None and time.monotonic() - hit[0] < _DNS_TTL_S:
        return hit[1]
    error: OSError | None = None
    for attempt in range(3):
        try:
            infos = sorted(
                _getaddrinfo(*args, **kwargs), key=lambda info: info[0] != socket.AF_INET
            )
        except socket.gaierror as exc:  # transient resolver failure
            error = exc
            time.sleep(0.3 * (attempt + 1))
            continue
        with _dns_lock:
            _dns_cache[key] = (time.monotonic(), infos)
        return infos
    if hit is not None:  # stale-if-error
        return hit[1]
    raise error  # type: ignore[misc]


socket.getaddrinfo = _ipv4_first

# Warm the cache for the providers in the background, so the first user does not pay.
_PROVIDER_HOSTS = (
    "archive-api.open-meteo.com",
    "power.larc.nasa.gov",
    "rest.isric.org",
    "esa-worldcover.s3.eu-central-1.amazonaws.com",
    "copernicus-dem-30m.s3.amazonaws.com",
    "nominatim.openstreetmap.org",
    "earth-search.aws.element84.com",
)


def _warm_dns() -> None:
    for host in _PROVIDER_HOSTS:
        with contextlib.suppress(OSError):
            socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)


threading.Thread(target=_warm_dns, name="dns-warm", daemon=True).start()


class SPAStaticFiles(StaticFiles):
    """Serve the bundle; unknown paths fall back to index.html (client routing)."""

    async def get_response(self, path: str, scope) -> Response:  # type: ignore[no-untyped-def]
        """Return the file, or index.html for extension-less SPA paths.

        Starlette raises ``HTTPException(404)`` for a missing file rather than
        returning a 404 response, so the fallback must catch, not inspect.
        """
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and "." not in path.rsplit("/", 1)[-1]:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and "." not in path.rsplit("/", 1)[-1]:
            response = await super().get_response("index.html", scope)
        return response


if DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=DIST, html=True), name="spa")
else:  # pragma: no cover - deployment guard

    @app.get("/")
    def _no_bundle(_: Request) -> dict[str, str]:
        return {"detail": "web/dist is missing - run `make web-build` first; API is at /docs"}
