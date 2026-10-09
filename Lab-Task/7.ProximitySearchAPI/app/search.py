"""Nearest-by-road search.

A location is valid if its straight-line distance from the query is <= rad.
Valid locations are ranked by the shortest road distance from the query's
nearest grid node. All road segments have the same length, so BFS gives the
shortest distances.
"""
import heapq
import math
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

# The CSV coordinates are rounded to 6 decimals (error up to 5e-7), so points
# lying exactly on the circle can come out slightly outside it.
EPS = 1e-6


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
        lat = np.array(net.lat)
        lon = np.array(net.lon)
        cats = np.array(net.cat)
        # coordinates of every location, grouped by category
        self.by_cat = {}
        for c in net.categories:
            nodes = np.flatnonzero(cats == c)
            self.by_cat[c] = (nodes, lat[nodes], lon[nodes])

    def count_in_radius(self, lat, lon, cat, rad):
        _, clat, clon = self.by_cat[cat]
        return int(np.count_nonzero(np.hypot(clat - lat, clon - lon) <= rad + EPS))

    def search(self, lat, lon, cat, rad, k=10, want_paths=False):
        start_time = time.perf_counter()
        net = self.net

        # If fewer than k places are inside the circle we can stop once we have
        # found all of them, instead of searching the whole map.
        need = min(k, self.count_in_radius(lat, lon, cat, rad))

        src = net.node_of(lat, lon)
        dist = {src: 0}
        parent = {src: -1}
        queue = deque([src])
        hits = []
        cutoff = None   # road distance of the need-th hit

        while queue and need > 0:
            v = queue.popleft()
            d = dist[v]
            # BFS pops nodes in order of distance, so once we are past the
            # distance of the need-th hit nothing closer can turn up. Nodes at
            # exactly that distance are still collected (ties).
            if cutoff is not None and d > cutoff:
                break

            if net.cat[v] == cat:
                e = math.hypot(net.lat[v] - lat, net.lon[v] - lon)
                if e <= rad + EPS:
                    hits.append(Hit(v, net.ids[v], d, e))
                    if len(hits) == need:
                        cutoff = d

            # Expand even outside the circle: the shortest road to a place
            # inside may go out and come back in.
            for w in net.adj[v]:
                if w not in dist:
                    dist[w] = d + 1
                    parent[w] = v
                    queue.append(w)

        # closest by road first, then by straight line, then lower ID
        hits.sort(key=lambda h: (h.hops, h.euclid, h.id))
        elapsed = (time.perf_counter() - start_time) * 1000
        return SearchResult(src, hits[:k], len(dist), need, elapsed, parent if want_paths else None)

    @staticmethod
    def path(result, node):
        """Nodes on the route from the query node to `node`."""
        route = []
        while node != -1:
            route.append(node)
            node = result.parent[node]
        return route[::-1]


def road_distances(net, src):
    """Dijkstra from src to every node. Slow; only used to check the BFS in tests."""
    dist = [math.inf] * net.size
    dist[src] = 0
    heap = [(0, src)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        for w in net.adj[v]:
            if d + 1 < dist[w]:
                dist[w] = d + 1
                heapq.heappush(heap, (d + 1, w))
    return dist


def rank_by(net, lat, lon, cat, rad, key, k=10):
    """Brute force: take every valid location and sort by key(node)."""
    found = []
    for v in range(net.size):
        if net.cat[v] != cat:
            continue
        e = math.hypot(net.lat[v] - lat, net.lon[v] - lon)
        if e <= rad + EPS:
            found.append((key(v), e, net.ids[v], v))
    found.sort()
    return found[:k]
