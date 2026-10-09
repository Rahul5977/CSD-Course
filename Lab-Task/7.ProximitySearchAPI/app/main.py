"""Proximity search API.

GET /search/?lat=..&long=..&cat=..&rad=..  ->  {"ids": [...10 location IDs...]}
Add debug=1 to also get distances and the route to every result.
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
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

_start = time.perf_counter()
net = load_network()
engine = ProximitySearch(net)
load_ms = (time.perf_counter() - _start) * 1000

app = FastAPI(title="Proximity Search API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


class BadRequest(Exception):
    pass


@app.exception_handler(BadRequest)
async def bad_request_handler(request, exc):
    return JSONResponse(status_code=400, content={"error": str(exc)})


def get_number(params, name):
    raw = params.get(name, "").strip()
    if not raw:
        raise BadRequest(f"missing required query parameter '{name}'")
    try:
        value = float(raw)
    except ValueError:
        raise BadRequest(f"'{name}' must be a number, got {raw!r}")
    if not math.isfinite(value):
        raise BadRequest(f"'{name}' must be finite")
    return value


def get_category(params):
    cat = params.get("cat", "").strip().lower()
    if not cat:
        raise BadRequest("missing required query parameter 'cat'")
    if cat not in engine.by_cat:
        raise BadRequest(f"unknown category {cat!r}; expected one of {net.categories}")
    return cat


def describe(result, lat, lon, cat, rad):
    """Extra output for debug=1."""
    src = result.source
    step = net.spacing
    rows = []
    for rank, hit in enumerate(result.hits, 1):
        v = hit.node
        road = hit.hops * step
        straight_from_src = math.hypot(net.lat[v] - net.lat[src], net.lon[v] - net.lon[src])
        rows.append({
            "rank": rank,
            "id": hit.id,
            "lat": net.lat[v],
            "long": net.lon[v],
            "category": net.cat[v],
            "road_segments": hit.hops,
            "road_distance": road,
            "straight_line": hit.euclid,
            "manhattan": abs(net.lat[v] - net.lat[src]) + abs(net.lon[v] - net.lon[src]),
            "detour_factor": road / straight_from_src if straight_from_src > 0 else 1.0,
            "route": [net.ids[u] for u in engine.path(result, v)],
        })

    info = {
        "query": {"lat": lat, "long": lon, "cat": cat, "rad": rad},
        "pickup_node": {
            "id": net.ids[src],
            "lat": net.lat[src],
            "long": net.lon[src],
            "snap_offset": math.hypot(net.lat[src] - lat, net.lon[src] - lon),
        },
        "matches_in_radius": result.in_radius,
        "nodes_explored": result.visited,
        "search_ms": round(result.elapsed_ms, 3),
        "results": rows,
    }
    if len(result.hits) < K:
        info["note"] = f"only {len(result.hits)} location(s) match inside the radius"
    return info


# Both paths are registered so /search does not get a 307 redirect.
@app.get("/search/")
@app.get("/search", include_in_schema=False)
async def search(request: Request):
    params = request.query_params
    lat = get_number(params, "lat")
    lon = get_number(params, "long")
    rad = get_number(params, "rad")
    cat = get_category(params)
    if rad < 0:
        raise BadRequest("'rad' must be >= 0")

    debug = params.get("debug", "").lower() in ("1", "true", "yes")
    result = engine.search(lat, lon, cat, rad, k=K, want_paths=debug)

    body = {"ids": [hit.id for hit in result.hits]}
    if debug:
        body.update(describe(result, lat, lon, cat, rad))
    return body


@app.get("/health")
def health():
    return {
        "status": "ok",
        "locations": net.size,
        "grid": f"{net.n}x{net.n}",
        "roads": net.n_links,
        "roads_missing": 2 * net.n * (net.n - 1) - net.n_links,
        "road_file": net.links_source,
        "categories": net.categories,
        "load_ms": round(load_ms, 1),
    }


@app.get("/network", include_in_schema=False)
def network():
    """Data for the map on the demo page."""
    cat_index = {c: i for i, c in enumerate(net.categories)}
    return {
        "n": net.n,
        "categories": net.categories,
        "cat": [cat_index[c] for c in net.cat],
        "ids": net.ids,
        "missing": net.missing_links(),
    }


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
