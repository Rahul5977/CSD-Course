"""Proximity Search API.

    GET /search/?lat=<float>&long=<float>&cat=<category>&rad=<float>
    -> {"ids": [10 location IDs, nearest by road first]}

Add &debug=1 for per-result road/straight-line distances and the driven route.
"""
import math
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .network import load_network
from .search import ProximitySearch

K = 10
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

t0 = time.perf_counter()
NET = load_network()
ENGINE = ProximitySearch(NET)
LOAD_MS = (time.perf_counter() - t0) * 1e3

app = FastAPI(title="Proximity Search API", version="1.0",
              description="Nearest locations by road-network distance inside a circular radius.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


class BadRequest(Exception):
    pass


def _number(params, name):
    raw = params.get(name)
    if raw is None or raw.strip() == "":
        raise BadRequest(f"missing required query parameter '{name}'")
    try:
        x = float(raw)
    except ValueError:
        raise BadRequest(f"'{name}' must be a number, got {raw!r}")
    if not math.isfinite(x):
        raise BadRequest(f"'{name}' must be finite")
    return x


def _flag(params, name):
    return params.get(name, "").strip().lower() in ("1", "true", "yes")


def _detour(road, a, b):
    crow = math.hypot(NET.lat[a] - NET.lat[b], NET.lon[a] - NET.lon[b])
    return road / crow if crow > 0 else 1.0


def _point(v):
    return {"lat": NET.lat[v], "long": NET.lon[v]}


@app.exception_handler(BadRequest)
async def bad_request(_, exc):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.get("/search/")
@app.get("/search", include_in_schema=False)
async def search(request: Request):  # sub-millisecond CPU work: no threadpool hop
    p = request.query_params
    lat, lon, rad = _number(p, "lat"), _number(p, "long"), _number(p, "rad")
    cat = (p.get("cat") or "").strip().lower()
    if not cat:
        raise BadRequest("missing required query parameter 'cat'")
    if cat not in ENGINE.by_cat:
        raise BadRequest(f"unknown category {cat!r}; expected one of {NET.categories}")
    if rad < 0:
        raise BadRequest("'rad' must be >= 0")

    debug = _flag(p, "debug")
    res = ENGINE.search(lat, lon, cat, rad, k=K, want_paths=debug)
    body = {"ids": [h.id for h in res.hits]}
    if not debug:
        return body

    h = NET.spacing
    src = res.source
    body.update({
        "query": {"lat": lat, "long": lon, "cat": cat, "rad": rad},
        "pickup_node": {"id": NET.ids[src], **_point(src),
                        "snap_offset": math.hypot(NET.lat[src] - lat, NET.lon[src] - lon)},
        "matches_in_radius": res.in_radius,
        "nodes_explored": res.visited,
        "search_ms": round(res.elapsed_ms, 3),
        "results": [{
            "rank": i + 1,
            "id": hit.id,
            **_point(hit.node),
            "category": NET.cat[hit.node],
            "road_segments": hit.hops,
            "road_distance": hit.hops * h,
            "straight_line": hit.euclid,
            "manhattan": abs(NET.lat[hit.node] - NET.lat[src]) + abs(NET.lon[hit.node] - NET.lon[src]),
            # road length vs straight line, both measured from the pickup intersection
            "detour_factor": _detour(hit.hops * h, src, hit.node),
            "route": [NET.ids[v] for v in ENGINE.path(res, hit.node)],
        } for i, hit in enumerate(res.hits)],
    })
    if len(res.hits) < K:
        body["note"] = f"only {len(res.hits)} reachable location(s) match inside the radius"
    return body


@app.get("/health")
def health():
    return {
        "status": "ok",
        "locations": NET.size,
        "grid": f"{NET.n}x{NET.n}",
        "roads": NET.n_links,
        "roads_missing": 2 * NET.n * (NET.n - 1) - NET.n_links,
        "road_file": NET.links_source,
        "categories": NET.categories,
        "load_ms": round(LOAD_MS, 1),
    }


@app.get("/network", include_in_schema=False)
def network():
    """Compact network dump for the demo map: category per node + missing roads."""
    idx = {c: i for i, c in enumerate(NET.categories)}
    return {
        "n": NET.n,
        "categories": NET.categories,
        "cat": [idx[c] for c in NET.cat],
        "ids": NET.ids,
        "missing": NET.missing_links(),
    }


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))
