"""Generates the numbers, tables and plots used in the report.

    .venv/bin/python scripts/analyze.py                 # everything
    .venv/bin/python scripts/analyze.py metrics latency # only some parts

Tables go to report/tables/*.tex, plots to results/charts/*.png and the raw
numbers to results/analysis.json.
"""
import collections
import json
import math
import os
import random
import statistics
import sys
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.network import RoadNetwork, load_network
from app.search import ProximitySearch, rank_by, road_distances

TABLE_DIR = os.path.join(ROOT, "report", "tables")
CHART_DIR = os.path.join(ROOT, "results", "charts")
os.makedirs(TABLE_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

net = load_network()
engine = ProximitySearch(net)
N = net.n
results = {}


def row_col(v):
    return divmod(v, N)


def manhattan_from(src):
    sr, sc = row_col(src)
    return lambda v: abs(v // N - sr) + abs(v % N - sc)


def percentile(values, p):
    values = sorted(values)
    return values[int(p * (len(values) - 1))]


def save_table(name, rows):
    """Writes the body rows of a LaTeX table; the header lives in report.tex."""
    with open(os.path.join(TABLE_DIR, name), "w") as f:
        for row in rows:
            f.write(" & ".join(str(x) for x in row) + r" \\" + "\n")


def save_chart(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, name), dpi=160)
    plt.close(fig)


def dataset():
    degree = collections.Counter(len(a) for a in net.adj)
    missing = net.missing_links()
    east_west = sum(1 for a, b in missing if b == a + 1)
    connected = all(math.isfinite(d) for d in road_distances(net, 0))
    possible = 2 * N * (N - 1)
    info = {
        "locations": net.size,
        "per_category": collections.Counter(net.cat).most_common(1)[0][1],
        "possible_roads": possible,
        "roads": net.n_links,
        "missing": len(missing),
        "missing_east_west": east_west,
        "connected": connected,
        "degree": dict(sorted(degree.items())),
        "loops": net.n_links - net.size + 1,
    }
    rows = [
        ("Locations", f"{net.size:,} on a {N}$\\times${N} grid, spacing $1/{N - 1}$"),
        ("Categories", f"{len(net.categories)} categories, {info['per_category']:,} locations each"),
        ("Possible roads between neighbours", f"{possible:,}"),
        ("Roads in \\texttt{link.txt}", f"{net.n_links:,} ({net.n_links / possible:.1%})".replace("%", "\\%")),
        ("Missing roads", f"{len(missing):,} ({east_west:,} east--west, {len(missing) - east_west:,} north--south)"),
        ("Connected components", "1" if connected else "more than 1"),
        ("Roads per intersection", ", ".join(f"{k}: {degree[k]:,}" for k in sorted(degree))),
        ("Independent loops (roads $-$ nodes $+$ 1)", f"{info['loops']:,}"),
    ]
    save_table("dataset.tex", rows)
    results["dataset"] = info


def detours(samples=200, seed=3):
    rng = random.Random(seed)
    ratios = []
    by_length = collections.defaultdict(list)
    for _ in range(samples):
        s = rng.randrange(net.size)
        dist = road_distances(net, s)
        manh = manhattan_from(s)
        for t in range(net.size):
            m = manh(t)
            if 0 < m <= 15:
                ratios.append(dist[t] / m)
                by_length[m].append(dist[t] / m)

    same = sum(r == 1 for r in ratios) / len(ratios)
    results["detour"] = {
        "pairs": len(ratios), "same_as_manhattan": same, "mean": statistics.fmean(ratios),
        "p90": percentile(ratios, 0.9), "p99": percentile(ratios, 0.99), "max": max(ratios),
    }
    d = results["detour"]
    save_table("detour.tex", [(f"{d['pairs']:,}", f"{same:.1%}".replace("%", "\\%"), f"{d['mean']:.2f}",
                               f"{d['p90']:.2f}", f"{d['p99']:.2f}", f"{d['max']:.1f}")])

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    ax[0].hist([min(r, 4) for r in ratios], bins=40, color="#4e79a7")
    ax[0].set_xlabel("road distance / Manhattan distance (capped at 4)")
    ax[0].set_ylabel("pairs")
    ax[0].set_title("Detours caused by missing roads")
    lengths = sorted(by_length)
    ax[1].plot(lengths, [sum(r == 1 for r in by_length[m]) / len(by_length[m]) for m in lengths],
               marker="o", color="#e15759")
    ax[1].set_xlabel("Manhattan distance (grid steps)")
    ax[1].set_ylabel("fraction with road = Manhattan")
    ax[1].set_ylim(0, 1)
    ax[1].set_title("Longer trips hit more missing roads")
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    save_chart(fig, "detour.png")


def one_way_network():
    """Same links, but read as one-way roads from A to B."""
    out = [[] for _ in range(net.size)]
    with open(os.path.join(ROOT, "data", "link.txt")) as f:
        for line in f:
            a, b, c, d = map(float, line.split())
            u = round(b * (N - 1)) * N + round(a * (N - 1))
            v = round(d * (N - 1)) * N + round(c * (N - 1))
            out[u].append(v)
    return RoadNetwork(N, net.ids, net.lat, net.lon, net.cat, [tuple(x) for x in out], net.categories)


def compare_metrics(queries=2000, seed=11):
    """How many marks would each way of ranking get?"""
    rng = random.Random(seed)
    one_way = one_way_network()
    names = ["Road network (this API)", "Euclidean", "Manhattan", "One-way roads"]
    scores = {name: [] for name in names}

    for i in range(queries):
        if i % 2 == 0:
            v = rng.randrange(net.size)
            lat, lon = net.lat[v], net.lon[v]
        else:
            lat, lon = rng.random(), rng.random()
        cat = rng.choice(net.categories)
        rad = rng.uniform(0.08, 0.35)
        if engine.count_in_radius(lat, lon, cat, rad) < 10:
            continue

        src = net.node_of(lat, lon)
        road = road_distances(net, src)
        directed = road_distances(one_way, src)
        tenth = rank_by(net, lat, lon, cat, rad, lambda v: road[v])[-1][0]

        answers = {
            "Road network (this API)": [h.id for h in engine.search(lat, lon, cat, rad).hits],
            "Euclidean": [r[2] for r in rank_by(net, lat, lon, cat, rad, lambda v: 0)],
            "Manhattan": [r[2] for r in rank_by(net, lat, lon, cat, rad, manhattan_from(src))],
            "One-way roads": [r[2] for r in rank_by(net, lat, lon, cat, rad, lambda v: directed[v])],
        }
        for name, ids in answers.items():
            # an ID scores if it is at least as close by road as the true 10th (ties are accepted)
            scores[name].append(sum(1 for x in ids if road[x - 1] <= tenth))

    n = len(scores[names[0]])
    rows = []
    for name in names:
        s = scores[name]
        full = sum(x == 10 for x in s) / n
        rows.append((name, f"{statistics.fmean(s) * 10:.1f}", f"{full:.1%}".replace("%", "\\%"), f"{min(s)}/10"))
    save_table("metrics.tex", rows)
    results["metric_comparison"] = {"queries": n, **{k: statistics.fmean(v) * 10 for k, v in scores.items()}}

    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    values = [statistics.fmean(scores[k]) * 10 for k in names]
    bars = ax.barh(names[::-1], values[::-1], color=["#9c755f", "#f28e2b", "#e15759", "#59a14f"])
    ax.bar_label(bars, fmt="%.1f", padding=3)
    ax.set_xlim(0, 108)
    ax.set_xlabel(f"expected marks out of 100 ({n:,} random queries)")
    ax.spines[["top", "right"]].set_visible(False)
    save_chart(fig, "metric_comparison.png")


def example(lat=0.74, lon=0.6, cat="bank", rad=0.1):
    res = engine.search(lat, lon, cat, rad, want_paths=True)
    src = res.source
    sr, sc = row_col(src)
    manh = rank_by(net, lat, lon, cat, rad, manhattan_from(src))
    chosen = {h.id for h in res.hits}
    manhattan_only = [r[3] for r in manh if r[2] not in chosen]

    r0, r1, c0, c1 = sr - 12, sr + 12, sc - 12, sc + 12
    inside = lambda v: r0 <= v // N <= r1 and c0 <= v % N <= c1
    missing = set(net.missing_links())

    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    for v in range(net.size):
        if not inside(v):
            continue
        r, c = row_col(v)
        if c + 1 < N and (v, v + 1) not in missing:
            ax.plot([c, c + 1], [r, r], color="#c9ced8", lw=0.9, zorder=1)
        if r + 1 < N and (v, v + N) not in missing:
            ax.plot([c, c], [r, r + 1], color="#c9ced8", lw=0.9, zorder=1)

    same_cat = [v for v in range(net.size) if net.cat[v] == cat and inside(v)]
    ax.scatter([v % N for v in same_cat], [v // N for v in same_cat], s=10, color="#76b7b2", zorder=2,
               label=f"{cat} locations")
    ax.add_patch(plt.Circle((lon * 99, lat * 99), rad * 99, fill=False, ls="--", color="#4e79a7", lw=1.4))
    for h in res.hits:
        route = engine.path(res, h.node)
        ax.plot([v % N for v in route], [v // N for v in route], color="#e0663a", lw=1.6, alpha=0.75, zorder=3)
    ax.scatter([h.node % N for h in res.hits], [h.node // N for h in res.hits], s=70, color="#e0663a",
               zorder=4, label="top 10 by road")
    ax.scatter([v % N for v in manhattan_only], [v // N for v in manhattan_only], s=90, facecolors="none",
               edgecolors="#1d2330", lw=1.6, zorder=5, label="Manhattan picks not in the top 10")
    ax.scatter([lon * 99], [lat * 99], marker="*", s=220, color="#1d2330", zorder=6, label="query")
    ax.set_xlim(c0 - 0.5, c1 + 0.5)
    ax.set_ylim(r0 - 0.5, r1 + 0.5)
    ax.set_aspect("equal")
    ax.set_xlabel("column (long x 99)")
    ax.set_ylabel("row (lat x 99)")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.95)
    ax.set_title(f"lat={lat}, long={lon}, cat={cat}, rad={rad}", fontsize=11)
    save_chart(fig, "example_query.png")

    rows = []
    for rank, h in enumerate(res.hits, 1):
        rows.append((rank, h.id, f"({net.lat[h.node]:.4f}, {net.lon[h.node]:.4f})", h.hops,
                     manhattan_from(src)(h.node), f"{h.euclid * 99:.2f}"))
    save_table("example.tex", rows)
    results["example"] = {"ids": [h.id for h in res.hits], "manhattan_ids": [r[2] for r in manh],
                          "manhattan_correct": 10 - len(manhattan_only)}


def latency(queries=5000, seed=5):
    rng = random.Random(seed)
    qs = []
    while len(qs) < queries:
        q = (rng.random(), rng.random(), rng.choice(net.categories), rng.uniform(0.06, 0.5))
        if engine.count_in_radius(*q) >= 10:
            qs.append(q)

    fast, explored = [], []
    for q in qs:
        t = time.perf_counter()
        r = engine.search(*q)
        fast.append((time.perf_counter() - t) * 1000)
        explored.append(r.visited)

    slow = []
    for q in qs[:300]:
        t = time.perf_counter()
        dist = road_distances(net, net.node_of(q[0], q[1]))
        rank_by(net, *q, key=lambda v: dist[v])
        slow.append((time.perf_counter() - t) * 1000)

    save_table("latency.tex", [
        ("BFS with early stop (API)", f"{percentile(fast, .5):.3f}", f"{percentile(fast, .95):.3f}",
         f"{percentile(fast, .99):.3f}", f"{statistics.fmean(explored):.0f}"),
        ("Dijkstra to all nodes + scan", f"{percentile(slow, .5):.2f}", f"{percentile(slow, .95):.2f}",
         f"{percentile(slow, .99):.2f}", f"{net.size:,}"),
    ])
    results["latency"] = {"bfs_p50": percentile(fast, .5), "bfs_p99": percentile(fast, .99),
                          "oracle_p50": percentile(slow, .5), "explored_mean": statistics.fmean(explored)}


def random_city(n, keep=0.75, seed=0):
    """n x n grid with a random spanning tree plus extra roads, like link.txt."""
    rng = random.Random(seed)
    edges = []
    for v in range(n * n):
        r, c = divmod(v, n)
        if c + 1 < n:
            edges.append((v, v + 1))
        if r + 1 < n:
            edges.append((v, v + n))
    rng.shuffle(edges)

    parent = list(range(n * n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    tree, extra = [], []
    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            tree.append((a, b))
        else:
            extra.append((a, b))
    roads = tree + extra[:max(0, int(keep * len(edges)) - len(tree))]

    adj = [[] for _ in range(n * n)]
    for a, b in roads:
        adj[a].append(b)
        adj[b].append(a)
    cats = sorted(net.categories)
    last = n - 1
    return RoadNetwork(n, list(range(1, n * n + 1)), [(v // n) / last for v in range(n * n)],
                       [(v % n) / last for v in range(n * n)], [rng.choice(cats) for _ in range(n * n)],
                       [tuple(a) for a in adj], cats, "random", len(roads))


def scaling(sizes=(100, 316, 1000), queries=2000):
    rows = []
    for n in sizes:
        t = time.perf_counter()
        city = random_city(n)
        city_engine = ProximitySearch(city)
        build = time.perf_counter() - t

        rng = random.Random(n)
        rad = 12 / (n - 1)
        times, explored = [], []
        for _ in range(queries):
            q = (rng.random(), rng.random(), rng.choice(city.categories), rad)
            t = time.perf_counter()
            r = city_engine.search(*q)
            times.append((time.perf_counter() - t) * 1000)
            explored.append(r.visited)
        rows.append((f"{n * n:,}", f"{city.n_links:,}", f"{build:.1f}", f"{percentile(times, .5):.3f}",
                     f"{percentile(times, .99):.3f}", f"{statistics.fmean(explored):.0f}"))
        print("  ", rows[-1], flush=True)
    save_table("scaling.tex", rows)
    results["scaling"] = rows


STEPS = {"dataset": dataset, "detour": detours, "metrics": compare_metrics,
         "example": example, "latency": latency, "scaling": scaling}

if __name__ == "__main__":
    for step in sys.argv[1:] or list(STEPS):
        print("running", step, flush=True)
        STEPS[step]()

    out = os.path.join(ROOT, "results", "analysis.json")
    saved = {}
    if os.path.exists(out):
        with open(out) as f:
            saved = json.load(f)
    saved.update(results)
    with open(out, "w") as f:
        json.dump(saved, f, indent=2, default=str)
