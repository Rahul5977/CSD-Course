"""Road network model: the 10,000 locations are intersections of an N x N lattice,
and link.txt lists which neighbouring intersections are joined by a road.

Node index = row * N + col, with row = round(lat * (N-1)) and col = round(lon * (N-1)).
Everything is held in plain Python lists because the search touches only a few
hundred nodes per query and list indexing beats numpy scalar access at that size.
"""
import csv
import math
import os
from dataclasses import dataclass, field

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
LOCATIONS_CSV = os.environ.get("LOCATIONS_CSV", os.path.join(DATA_DIR, "locations.csv"))
LINKS_TXT = os.environ.get("LINKS_TXT", os.path.join(DATA_DIR, "link.txt"))

COORD_TOL = 1e-4  # CSV coordinates are rounded to 6 dp; the grid spacing is ~0.0101


@dataclass
class RoadNetwork:
    n: int                      # lattice side (100)
    ids: list                   # node -> location ID
    lat: list                   # node -> latitude
    lon: list                   # node -> longitude
    cat: list                   # node -> category string
    adj: list                   # node -> tuple of neighbour nodes (undirected roads)
    categories: list = field(default_factory=list)
    links_source: str = ""
    n_links: int = 0

    @property
    def size(self):
        return self.n * self.n

    @property
    def spacing(self):
        return 1.0 / (self.n - 1)

    def node_of(self, lat, lon):
        """Nearest lattice node to an arbitrary point (map-matching a GPS fix).

        Rounding each axis independently gives the Euclidean-nearest lattice node;
        points outside the unit square are clamped onto the boundary.
        """
        last = self.n - 1
        r = min(max(int(math.floor(lat * last + 0.5)), 0), last)
        c = min(max(int(math.floor(lon * last + 0.5)), 0), last)
        return r * self.n + c

    def missing_links(self):
        """Lattice edges that have no road (used by the demo map and the report)."""
        out = []
        n = self.n
        for v in range(self.size):
            r, c = divmod(v, n)
            nb = self.adj[v]
            if c + 1 < n and v + 1 not in nb:
                out.append((v, v + 1))
            if r + 1 < n and v + n not in nb:
                out.append((v, v + n))
        return out


def _grid_index(value, last):
    idx = round(value * last)
    if abs(idx / last - value) > COORD_TOL or not 0 <= idx <= last:
        raise ValueError(f"coordinate {value} is not on the {last + 1}-point lattice")
    return idx


def load_locations(path=LOCATIONS_CSV):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    n = math.isqrt(len(rows))
    if n * n != len(rows):
        raise ValueError(f"{len(rows)} locations do not form a square lattice")
    last = n - 1
    ids, lat, lon, cat = [None] * len(rows), [0.0] * len(rows), [0.0] * len(rows), [""] * len(rows)
    for row in rows:
        la, lo = float(row["Latitude"]), float(row["Longitude"])
        v = _grid_index(la, last) * n + _grid_index(lo, last)
        if ids[v] is not None:
            raise ValueError(f"two locations map to lattice node {v}")
        ids[v], lat[v], lon[v] = int(row["ID"]), la, lo
        cat[v] = row["Category"].strip().lower()
    return n, ids, lat, lon, cat


def load_links(path, n):
    """Parse `lon_a lat_a lon_b lat_b` lines into an undirected adjacency list.

    The file lists every road once in canonical order (A < B), so roads are
    two-way; duplicates are ignored and non-neighbour pairs are rejected.
    """
    last = n - 1
    nbrs = [set() for _ in range(n * n)]
    count = 0
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            parts = line.split()
            if not parts:
                continue
            if len(parts) != 4:
                raise ValueError(f"{path}:{lineno}: expected 4 numbers, got {len(parts)}")
            lon_a, lat_a, lon_b, lat_b = map(float, parts)
            ra, ca = _grid_index(lat_a, last), _grid_index(lon_a, last)
            rb, cb = _grid_index(lat_b, last), _grid_index(lon_b, last)
            if abs(ra - rb) + abs(ca - cb) != 1:
                raise ValueError(f"{path}:{lineno}: link is not between grid neighbours")
            u, v = ra * n + ca, rb * n + cb
            if v not in nbrs[u]:
                count += 1
            nbrs[u].add(v)
            nbrs[v].add(u)
    return [tuple(sorted(s)) for s in nbrs], count


def full_lattice(n):
    """Every neighbour pair connected: graph distance == Manhattan distance."""
    adj = []
    for v in range(n * n):
        r, c = divmod(v, n)
        nb = []
        if r > 0: nb.append(v - n)
        if c > 0: nb.append(v - 1)
        if c + 1 < n: nb.append(v + 1)
        if r + 1 < n: nb.append(v + n)
        adj.append(tuple(nb))
    return adj, 2 * n * (n - 1)


def load_network(locations=LOCATIONS_CSV, links=LINKS_TXT):
    n, ids, lat, lon, cat = load_locations(locations)
    if links and os.path.exists(links):
        adj, n_links = load_links(links, n)
        source = os.path.basename(links)
    else:
        adj, n_links = full_lattice(n)
        source = "full-lattice (no link file)"
    return RoadNetwork(n=n, ids=ids, lat=lat, lon=lon, cat=cat, adj=adj,
                       categories=sorted(set(cat)), links_source=source, n_links=n_links)
