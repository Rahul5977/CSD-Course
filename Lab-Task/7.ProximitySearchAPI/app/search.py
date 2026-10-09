"""Proximity search on the road network.

Two distances, two jobs (exactly as the brief separates them):
  * validity  - the straight-line ("circular") distance from the query point must be <= rad;
  * closeness - the shortest drivable distance along roads from the query's nearest
                intersection, i.e. the number of road segments x grid spacing.

Every road segment has the same length, so the shortest path is a breadth-first
search. BFS settles nodes in non-decreasing road distance, which lets us stop as soon
as the level containing the k-th match has been fully scanned: nothing found later can
be closer. Paths may leave the radius circle and come back, so the BFS is never pruned
by the circle - only the *results* are.
"""
import heapq
import math
import time
from dataclasses import dataclass

import numpy as np

RADIUS_EPS = 1e-6  # CSV coordinates carry up to 5e-7 rounding; keep points that lie on the circle


@dataclass
class Hit:
    node: int
    id: int
    hops: int
    euclid: float


@dataclass
class SearchResult:
    source: int
    hits: list
    visited: int
    in_radius: int
    elapsed_ms: float
    parent: dict = None


class ProximitySearch:
    def __init__(self, net):
        self.net = net
        self.size = net.size
        # Per-category coordinate arrays: count candidates inside the circle in O(n_cat)
        # with numpy, so the BFS can stop the moment it has found all of them.
        self.by_cat = {}
        lat, lon = np.array(net.lat), np.array(net.lon)
        cats = np.array(net.cat)
        for c in net.categories:
            nodes = np.flatnonzero(cats == c)
            self.by_cat[c] = (nodes, lat[nodes], lon[nodes])

    def count_in_radius(self, lat, lon, cat, rad):
        _, la, lo = self.by_cat[cat]
        return int(np.count_nonzero(np.hypot(la - lat, lo - lon) <= rad + RADIUS_EPS))

    def search(self, lat, lon, cat, rad, k=10, want_paths=False):
        t0 = time.perf_counter()
        net = self.net
        adj, ncat, nlat, nlon, ids = net.adj, net.cat, net.lat, net.lon, net.ids
        limit = rad + RADIUS_EPS
        target = min(k, self.count_in_radius(lat, lon, cat, rad))

        src = net.node_of(lat, lon)
        seen = bytearray(self.size)
        seen[src] = 1
        parent = {src: -1} if want_paths else None
        frontier = [src]
        hits = []
        visited = 0
        hops = 0
        while frontier and len(hits) < target:
            visited += len(frontier)
            for v in frontier:
                if ncat[v] == cat:
                    e = math.hypot(nlat[v] - lat, nlon[v] - lon)
                    if e <= limit:
                        hits.append(Hit(v, ids[v], hops, e))
            if len(hits) >= target:
                break  # the whole tie level is in `hits`; later levels are strictly farther
            nxt = []
            for v in frontier:
                for w in adj[v]:
                    if not seen[w]:
                        seen[w] = 1
                        nxt.append(w)
                        if parent is not None:
                            parent[w] = v
            frontier = nxt
            hops += 1

        # Road distance first; among equal road distances prefer the one that is
        # physically nearer, then the lower ID so the answer is deterministic.
        hits.sort(key=lambda h: (h.hops, h.euclid, h.id))
        return SearchResult(src, hits[:k], visited, target, (time.perf_counter() - t0) * 1e3, parent)

    def path(self, result, node):
        """Intersections along the shortest route from the source to `node`."""
        out = []
        while node != -1:
            out.append(node)
            node = result.parent[node]
        return out[::-1]


def road_distances(net, src):
    """All-node shortest road distances via Dijkstra (independent oracle for tests)."""
    dist = [math.inf] * net.size
    dist[src] = 0
    pq = [(0, src)]
    while pq:
        d, v = heapq.heappop(pq)
        if d > dist[v]:
            continue
        for w in net.adj[v]:
            if d + 1 < dist[w]:
                dist[w] = d + 1
                heapq.heappush(pq, (d + 1, w))
    return dist


def rank_by(net, lat, lon, cat, rad, key, k=10):
    """Brute force: filter every location by the circle, rank by `key(node)`.

    Used as the correctness oracle (key = road distance) and to compare the
    alternative metrics (Euclidean / Manhattan) in the report.
    """
    cands = []
    for v in range(net.size):
        if net.cat[v] != cat:
            continue
        e = math.hypot(net.lat[v] - lat, net.lon[v] - lon)
        if e <= rad + RADIUS_EPS:
            cands.append((key(v), e, net.ids[v], v))
    cands.sort()
    return cands[:k]
