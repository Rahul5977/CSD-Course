import math
import os
import random

import pytest

from app.network import full_lattice, load_links, load_network
from app.search import ProximitySearch, rank_by, road_distances

ROOT = os.path.join(os.path.dirname(__file__), "..")
NET = load_network()
ENGINE = ProximitySearch(NET)


def as_tuples(res):
    return [(h.hops, h.euclid, h.id) for h in res.hits]


def oracle(net, lat, lon, cat, rad):
    d = road_distances(net, net.node_of(lat, lon))
    return [(a, b, c) for a, b, c, _ in rank_by(net, lat, lon, cat, rad, lambda v: d[v])]


def test_dataset_shape():
    assert NET.n == 100 and NET.size == 10_000
    assert NET.links_source == "link.txt"
    assert NET.n_links == 14_800
    assert len(NET.categories) == 8
    # node index encodes the lattice position and IDs follow row-major order
    assert all(NET.ids[v] == v + 1 for v in range(NET.size))


def test_network_is_connected():
    d = road_distances(NET, 0)
    assert all(math.isfinite(x) for x in d)


@pytest.mark.parametrize("seed", range(4))
def test_matches_dijkstra_oracle(seed):
    rng = random.Random(seed)
    for i in range(400):
        lat, lon = rng.random(), rng.random()
        if i % 2:
            lat, lon = round(lat * 99) / 99, round(lon * 99) / 99
        cat = rng.choice(NET.categories)
        rad = rng.choice([0.02, 0.04, 0.06, 0.1, 0.15, 0.25, 0.5, 2.0])
        assert as_tuples(ENGINE.search(lat, lon, cat, rad)) == oracle(NET, lat, lon, cat, rad)


def test_always_ten_when_ten_qualify():
    rng = random.Random(42)
    for _ in range(300):
        lat, lon, cat = rng.random(), rng.random(), rng.choice(NET.categories)
        rad = rng.choice([0.08, 0.15, 0.3, 1.5])
        res = ENGINE.search(lat, lon, cat, rad)
        assert len(res.hits) == min(10, ENGINE.count_in_radius(lat, lon, cat, rad))


def test_results_respect_radius_and_category():
    res = ENGINE.search(0.3, 0.7, "hospital", 0.12)
    for h in res.hits:
        assert NET.cat[h.node] == "hospital"
        assert math.hypot(NET.lat[h.node] - 0.3, NET.lon[h.node] - 0.7) <= 0.12 + 1e-6
    hops = [h.hops for h in res.hits]
    assert hops == sorted(hops)


def test_point_exactly_on_circle_is_included():
    # node (50, 53) is exactly 3 grid steps from node (50, 50)
    lat, lon = 50 / 99, 50 / 99
    v = 50 * 100 + 53
    cat = NET.cat[v]
    res = ENGINE.search(lat, lon, cat, 3 / 99, k=50)
    assert v in [h.node for h in res.hits]


def test_corner_query_and_off_grid_clamping():
    a = ENGINE.search(0.0, 0.0, "bank", 0.2)
    b = ENGINE.search(-0.3, -0.1, "bank", 0.6)  # outside the square: snaps to the corner
    assert a.source == b.source == 0
    assert len(a.hits) == 10


def test_road_distance_differs_from_manhattan_somewhere():
    """The point of the assignment: missing roads change the ranking."""
    rng = random.Random(1)
    differ = 0
    for _ in range(200):
        lat, lon, cat = rng.random(), rng.random(), rng.choice(NET.categories)
        road = [h.id for h in ENGINE.search(lat, lon, cat, 0.2).hits]
        src = NET.node_of(lat, lon)
        manh = lambda v: abs(v // 100 - src // 100) + abs(v % 100 - src % 100)
        if road != [c for _, _, c, _ in rank_by(NET, lat, lon, cat, 0.2, manh)]:
            differ += 1
    assert differ > 50


# ---- tiny hand-made network: a wall of missing roads forces a detour ----------

def tiny(tmp_path, links):
    """3x3 lattice, all locations 'cafe' except where noted."""
    loc = tmp_path / "loc.csv"
    rows = ["ID,Latitude,Longitude,Category"]
    for r in range(3):
        for c in range(3):
            rows.append(f"{r * 3 + c + 1},{r / 2},{c / 2},{'bank' if (r, c) == (0, 0) else 'cafe'}")
    loc.write_text("\n".join(rows) + "\n")
    lk = tmp_path / "link.txt"
    lk.write_text("\n".join(f"{c1 / 2} {r1 / 2} {c2 / 2} {r2 / 2}" for (r1, c1), (r2, c2) in links) + "\n")
    return load_network(str(loc), str(lk))


def test_missing_link_forces_detour(tmp_path):
    # Roads: (0,0)-(1,0)-(2,0)-(2,1)-(2,2)-(1,2)-(0,2)-(0,1) ring; (1,1) joined to (2,1).
    # (0,0)-(0,1) is missing, so (0,1) is 1 step away as the crow flies but 7 by road.
    ring = [((0, 0), (1, 0)), ((1, 0), (2, 0)), ((2, 0), (2, 1)), ((2, 1), (2, 2)),
            ((2, 2), (1, 2)), ((1, 2), (0, 2)), ((0, 2), (0, 1)), ((1, 1), (2, 1))]
    net = tiny(tmp_path, ring)
    res = ProximitySearch(net).search(0.0, 0.0, "cafe", 5.0, k=8)
    order = [(h.id, h.hops) for h in res.hits]
    assert order == [(4, 1), (7, 2), (8, 3), (5, 4), (9, 4), (6, 5), (3, 6), (2, 7)]


def test_unreachable_nodes_are_never_returned(tmp_path):
    net = tiny(tmp_path, [((0, 0), (1, 0))])
    res = ProximitySearch(net).search(0.0, 0.0, "cafe", 5.0)
    assert [h.id for h in res.hits] == [4]


def test_link_parser_rejects_diagonals(tmp_path):
    p = tmp_path / "bad.txt"
    p.write_text("0 0 0.5 0.5\n")
    with pytest.raises(ValueError):
        load_links(str(p), 3)


def test_full_lattice_fallback_equals_manhattan():
    adj, n_links = full_lattice(100)
    assert n_links == 19_800
    net = load_network(links="")
    assert net.adj == adj
    eng = ProximitySearch(net)
    d = road_distances(net, net.node_of(0.42, 0.61))
    src = net.node_of(0.42, 0.61)
    assert all(d[v] == abs(v // 100 - src // 100) + abs(v % 100 - src % 100) for v in range(net.size))
    assert len(eng.search(0.42, 0.61, "park", 0.2).hits) == 10
