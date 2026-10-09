import math
import random

import pytest

from app.network import full_grid, load_network, read_links
from app.search import ProximitySearch, rank_by, road_distances

net = load_network()
engine = ProximitySearch(net)


def brute_force(network, lat, lon, cat, rad):
    """Expected answer: Dijkstra to every node, then sort all valid locations."""
    dist = road_distances(network, network.node_of(lat, lon))
    return [(d, e, i) for d, e, i, _ in rank_by(network, lat, lon, cat, rad, lambda v: dist[v])]


def as_tuples(result):
    return [(h.hops, h.euclid, h.id) for h in result.hits]


def manhattan_from(src):
    return lambda v: abs(v // 100 - src // 100) + abs(v % 100 - src % 100)


def test_dataset():
    assert net.n == 100
    assert net.size == 10000
    assert net.links_source == "link.txt"
    assert net.n_links == 14800
    assert len(net.categories) == 8
    assert all(net.ids[v] == v + 1 for v in range(net.size))


def test_every_location_is_reachable():
    assert all(math.isfinite(d) for d in road_distances(net, 0))


@pytest.mark.parametrize("seed", range(4))
def test_bfs_matches_brute_force(seed):
    rng = random.Random(seed)
    for i in range(400):
        lat, lon = rng.random(), rng.random()
        if i % 2:
            # half of the queries exactly on a grid node
            lat, lon = round(lat * 99) / 99, round(lon * 99) / 99
        cat = rng.choice(net.categories)
        rad = rng.choice([0.02, 0.04, 0.06, 0.1, 0.15, 0.25, 0.5, 2.0])
        assert as_tuples(engine.search(lat, lon, cat, rad)) == brute_force(net, lat, lon, cat, rad)


def test_returns_ten_when_ten_exist():
    rng = random.Random(42)
    for _ in range(300):
        lat, lon, cat = rng.random(), rng.random(), rng.choice(net.categories)
        rad = rng.choice([0.08, 0.15, 0.3, 1.5])
        result = engine.search(lat, lon, cat, rad)
        assert len(result.hits) == min(10, engine.count_in_radius(lat, lon, cat, rad))


def test_results_are_valid_and_sorted():
    result = engine.search(0.3, 0.7, "hospital", 0.12)
    for h in result.hits:
        assert net.cat[h.node] == "hospital"
        assert math.hypot(net.lat[h.node] - 0.3, net.lon[h.node] - 0.7) <= 0.12 + 1e-6
    hops = [h.hops for h in result.hits]
    assert hops == sorted(hops)


def test_point_on_the_circle_is_included():
    # node (50, 53) is exactly 3 steps east of node (50, 50)
    v = 50 * 100 + 53
    result = engine.search(50 / 99, 50 / 99, net.cat[v], 3 / 99, k=50)
    assert v in [h.node for h in result.hits]


def test_corner_and_outside_points():
    a = engine.search(0.0, 0.0, "bank", 0.2)
    b = engine.search(-0.3, -0.1, "bank", 0.6)
    assert a.source == b.source == 0
    assert len(a.hits) == 10


def test_road_ranking_differs_from_manhattan():
    rng = random.Random(1)
    different = 0
    for _ in range(200):
        lat, lon, cat = rng.random(), rng.random(), rng.choice(net.categories)
        road = [h.id for h in engine.search(lat, lon, cat, 0.2).hits]
        manh = rank_by(net, lat, lon, cat, 0.2, manhattan_from(net.node_of(lat, lon)))
        if road != [i for _, _, i, _ in manh]:
            different += 1
    assert different > 50


# Small 3x3 networks. Node (0,0) is a bank, everything else is a cafe.

def make_town(tmp_path, roads):
    rows = ["ID,Latitude,Longitude,Category"]
    for r in range(3):
        for c in range(3):
            cat = "bank" if (r, c) == (0, 0) else "cafe"
            rows.append(f"{r * 3 + c + 1},{r / 2},{c / 2},{cat}")
    locations = tmp_path / "locations.csv"
    locations.write_text("\n".join(rows) + "\n")

    lines = [f"{c1 / 2} {r1 / 2} {c2 / 2} {r2 / 2}" for (r1, c1), (r2, c2) in roads]
    links = tmp_path / "link.txt"
    links.write_text("\n".join(lines) + "\n")
    return load_network(str(locations), str(links))


def test_missing_road_forces_a_detour(tmp_path):
    # A ring around the outside plus (1,1)-(2,1). The road (0,0)-(0,1) is
    # missing, so (0,1) is one step away in a straight line but 7 by road.
    roads = [((0, 0), (1, 0)), ((1, 0), (2, 0)), ((2, 0), (2, 1)), ((2, 1), (2, 2)),
             ((2, 2), (1, 2)), ((1, 2), (0, 2)), ((0, 2), (0, 1)), ((1, 1), (2, 1))]
    town = make_town(tmp_path, roads)
    result = ProximitySearch(town).search(0.0, 0.0, "cafe", 5.0, k=8)
    assert [(h.id, h.hops) for h in result.hits] == [
        (4, 1), (7, 2), (8, 3), (5, 4), (9, 4), (6, 5), (3, 6), (2, 7)]


def test_unreachable_places_are_skipped(tmp_path):
    town = make_town(tmp_path, [((0, 0), (1, 0))])
    result = ProximitySearch(town).search(0.0, 0.0, "cafe", 5.0)
    assert [h.id for h in result.hits] == [4]


def test_diagonal_link_is_rejected(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("0 0 0.5 0.5\n")
    with pytest.raises(ValueError):
        read_links(str(bad), 3)


def test_without_link_file_distance_is_manhattan():
    adj, count = full_grid(100)
    assert count == 19800
    grid = load_network(links="")
    assert grid.adj == adj

    src = grid.node_of(0.42, 0.61)
    dist = road_distances(grid, src)
    manh = manhattan_from(src)
    assert all(dist[v] == manh(v) for v in range(grid.size))
    assert len(ProximitySearch(grid).search(0.42, 0.61, "park", 0.2).hits) == 10
