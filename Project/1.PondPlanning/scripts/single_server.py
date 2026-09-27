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
import json
import os
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
# Last good IPv4 address per host, kept on disk (POND_DNS_CACHE) so that a restarted
# replica can still reach a provider while the resolver is failing.
_DNS_FILE = os.environ.get("POND_DNS_CACHE")
_known_ips: dict[str, list[str]] = {}
if _DNS_FILE:
    with contextlib.suppress(OSError, ValueError):
        _known_ips = json.loads(Path(_DNS_FILE).read_text())


def _remember(host: str, infos: Any) -> None:
    ips = sorted({info[4][0] for info in infos if info[0] == socket.AF_INET})
    if not _DNS_FILE or not ips or _known_ips.get(host) == ips:
        return
    with _dns_lock:
        _known_ips[host] = ips
        with contextlib.suppress(OSError):
            Path(_DNS_FILE).write_text(json.dumps(_known_ips))


def _from_disk(host: Any, port: Any) -> Any:
    ips = _known_ips.get(host) if isinstance(host, str) else None
    if not ips:
        return None
    number = int(port) if isinstance(port, int | str) and str(port).isdigit() else 443
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, number)) for ip in ips]


# Address that last accepted a connection, per host. From the lab only 2 of S3's 7
# addresses answer; putting the one that worked first saves a timeout per connection.
_good_ip: dict[str, str] = {}


def _good_first(host: Any, infos: Any) -> Any:
    good = _good_ip.get(host) if isinstance(host, str) else None
    return sorted(infos, key=lambda info: info[4][0] != good) if good else infos


def _ipv4_first(*args: Any, **kwargs: Any) -> Any:
    return _good_first(args[0] if args else None, _lookup(*args, **kwargs))


def _lookup(*args: Any, **kwargs: Any) -> Any:
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
        if args:
            _remember(args[0], infos)
        return infos
    if hit is not None:  # stale-if-error
        return hit[1]
    disk = _from_disk(args[0], args[1] if len(args) > 1 else kwargs.get("port")) if args else None
    if disk is not None:  # stale-if-error across restarts
        return disk
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


# GDAL reads the elevation tiles through its own libcurl, which does its own DNS and so
# bypasses the cache above; on the lab VMs that failed area analyses ("Could not resolve
# host"). A proxy makes curl skip DNS entirely: it sends "CONNECT host:443" to us, we
# resolve the host through the cached, retrying lookup and pass the bytes through. TLS
# stays end to end between GDAL and the server — the proxy never sees plaintext.
def _start_connect_proxy() -> None:
    import asyncio

    async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        with contextlib.suppress(Exception):
            while data := await reader.read(65536):
                writer.write(data)
                await writer.drain()
        with contextlib.suppress(Exception):
            writer.close()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = (await reader.readline()).decode("latin-1").split()
            while (await reader.readline()) not in (b"\r\n", b"\n", b""):
                pass
            if len(request) < 2 or request[0].upper() != "CONNECT":
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                await writer.drain()
                writer.close()
                return
            host, _, port = request[1].rpartition(":")
            loop = asyncio.get_running_loop()
            infos = await loop.run_in_executor(
                None, lambda: socket.getaddrinfo(host, int(port), type=socket.SOCK_STREAM)
            )
            # Try each address with a short timeout, as curl itself would; remember the
            # one that answered so the next connection goes there first.
            for address in dict.fromkeys(info[4][0] for info in infos):
                try:
                    up_reader, up_writer = await asyncio.wait_for(
                        asyncio.open_connection(address, int(port)), timeout=3
                    )
                except (OSError, TimeoutError):
                    continue
                _good_ip[host] = address
                break
            else:
                raise OSError(f"no address of {host} accepted a connection")
        except Exception:
            with contextlib.suppress(Exception):
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
                writer.close()
            return
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()
        await asyncio.gather(pipe(reader, up_writer), pipe(up_reader, writer))

    loop = asyncio.new_event_loop()
    server = loop.run_until_complete(asyncio.start_server(handle, "127.0.0.1", 0))
    port = server.sockets[0].getsockname()[1]
    os.environ["GDAL_HTTP_PROXY"] = f"127.0.0.1:{port}"
    threading.Thread(target=loop.run_forever, name="gdal-connect-proxy", daemon=True).start()


if not os.environ.get("GDAL_HTTP_PROXY"):
    _start_connect_proxy()


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
