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

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from app.main import app

DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


class SPAStaticFiles(StaticFiles):
    """Serve the bundle; unknown paths fall back to index.html (client routing)."""

    async def get_response(self, path: str, scope) -> Response:  # type: ignore[no-untyped-def]
        """Return the file, or index.html for extension-less SPA paths."""
        response = await super().get_response(path, scope)
        if response.status_code == 404 and "." not in path.rsplit("/", 1)[-1]:
            response = await super().get_response("index.html", scope)
        return response


if DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=DIST, html=True), name="spa")
else:  # pragma: no cover - deployment guard

    @app.get("/")
    def _no_bundle(_: Request) -> dict[str, str]:
        return {"detail": "web/dist is missing - run `make web-build` first; API is at /docs"}
