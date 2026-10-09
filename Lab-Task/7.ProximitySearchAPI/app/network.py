"""Loads the locations and the road links into a graph.

The locations sit on an N x N grid, so every location gets a node number
node = row * N + col, where row = lat * (N - 1) and col = long * (N - 1).
"""
import csv
import math
import os
from dataclasses import dataclass, field

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
LOCATIONS_CSV = os.environ.get("LOCATIONS_CSV", os.path.join(DATA_DIR, "locations.csv"))
LINKS_TXT = os.environ.get("LINKS_TXT", os.path.join(DATA_DIR, "link.txt"))

# coordinates in the files are rounded to 6 decimals, grid spacing is ~0.0101
TOLERANCE = 1e-4


@dataclass
class RoadNetwork:
    n: int          # grid side
    ids: list       # node -> location ID
    lat: list
    lon: list
    cat: list
    adj: list       # node -> neighbouring nodes
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
        """Nearest grid node to (lat, lon). Points outside the grid are clamped to the border."""
        last = self.n - 1
        row = min(max(math.floor(lat * last + 0.5), 0), last)
        col = min(max(math.floor(lon * last + 0.5), 0), last)
        return row * self.n + col

    def missing_links(self):
        """Pairs of neighbouring nodes that have no road between them."""
        n = self.n
        missing = []
        for v in range(self.size):
            row, col = divmod(v, n)
            if col + 1 < n and v + 1 not in self.adj[v]:
                missing.append((v, v + 1))
            if row + 1 < n and v + n not in self.adj[v]:
                missing.append((v, v + n))
        return missing


def to_grid(value, last):
    idx = round(value * last)
    if not 0 <= idx <= last or abs(idx / last - value) > TOLERANCE:
        raise ValueError(f"{value} is not a grid coordinate")
    return idx


def read_locations(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    n = math.isqrt(len(rows))
    if n * n != len(rows):
        raise ValueError(f"expected a square grid, got {len(rows)} locations")

    ids = [None] * len(rows)
    lat = [0.0] * len(rows)
    lon = [0.0] * len(rows)
    cat = [""] * len(rows)
    for row in rows:
        la, lo = float(row["Latitude"]), float(row["Longitude"])
        v = to_grid(la, n - 1) * n + to_grid(lo, n - 1)
        if ids[v] is not None:
            raise ValueError(f"duplicate location at node {v}")
        ids[v] = int(row["ID"])
        lat[v] = la
        lon[v] = lo
        cat[v] = row["Category"].strip().lower()
    return n, ids, lat, lon, cat


def read_links(path, n):
    """Each line is 'long_a lat_a long_b lat_b'. Roads are two-way."""
    last = n - 1
    neighbours = [set() for _ in range(n * n)]
    count = 0
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            parts = line.split()
            if not parts:
                continue
            if len(parts) != 4:
                raise ValueError(f"line {lineno}: expected 4 values")
            lon_a, lat_a, lon_b, lat_b = map(float, parts)
            ra, ca = to_grid(lat_a, last), to_grid(lon_a, last)
            rb, cb = to_grid(lat_b, last), to_grid(lon_b, last)
            if abs(ra - rb) + abs(ca - cb) != 1:
                raise ValueError(f"line {lineno}: points are not neighbours")
            a, b = ra * n + ca, rb * n + cb
            if b not in neighbours[a]:
                count += 1
            neighbours[a].add(b)
            neighbours[b].add(a)
    return [tuple(sorted(s)) for s in neighbours], count


def full_grid(n):
    """Every neighbour connected. Used when there is no link file."""
    adj = []
    for v in range(n * n):
        row, col = divmod(v, n)
        nb = []
        if row > 0:
            nb.append(v - n)
        if col > 0:
            nb.append(v - 1)
        if col + 1 < n:
            nb.append(v + 1)
        if row + 1 < n:
            nb.append(v + n)
        adj.append(tuple(nb))
    return adj, 2 * n * (n - 1)


def load_network(locations=LOCATIONS_CSV, links=LINKS_TXT):
    n, ids, lat, lon, cat = read_locations(locations)
    if links and os.path.exists(links):
        adj, n_links = read_links(links, n)
        source = os.path.basename(links)
    else:
        adj, n_links = full_grid(n)
        source = "full grid (no link file)"
    return RoadNetwork(n, ids, lat, lon, cat, adj, sorted(set(cat)), source, n_links)
