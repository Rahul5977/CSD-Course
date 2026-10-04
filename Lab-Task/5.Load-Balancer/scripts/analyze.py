#!/usr/bin/env python3
"""
analyze.py — aggregate results/raw/*.json into:
  results/processed/summary.csv        every run, one row
  results/processed/medians.csv        median-of-reps per (config, concurrency)
  report/comparison_table.md           the assignment's comparison table
  results/charts/*.png                 charts (matplotlib; falls back to SVG)

Every number traces to run ids; nothing is fabricated. Run on the Mac:
  python3 scripts/analyze.py            (or with the venv python for charts)
"""
import csv
import glob
import json
import os
import statistics
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "results", "raw")
OUT = os.path.join(ROOT, "results", "processed")
CHARTS = os.path.join(ROOT, "results", "charts")
os.makedirs(OUT, exist_ok=True)
os.makedirs(CHARTS, exist_ok=True)

runs = []
for path in sorted(glob.glob(os.path.join(RAW, "*.json"))):
    with open(path) as fh:
        s = json.load(fh)["summary"]
    rid = s["run_id"]
    if rid.startswith(("local_", "calibration")):
        continue                          # local smoke runs are not experiment data
    cfg = rid.split("_c")[0] if "_c" in rid else rid.split("_")[0]
    runs.append({
        "run_id": rid, "config": cfg, "concurrency": s["concurrency"],
        "total": s["total_requests"], "success": s["success"], "errors": s["errors"],
        "error_pct": s["error_rate_pct"], "rps": s["throughput_rps"],
        "mean": s["latency_ms"]["mean"], "stddev": s["latency_ms"]["stddev"],
        "min": s["latency_ms"]["min"], "p50": s["latency_ms"]["p50"],
        "p90": s["latency_ms"]["p90"], "p95": s["latency_ms"]["p95"],
        "p99": s["latency_ms"]["p99"], "max": s["latency_ms"]["max"],
        "dist": s["backend_distribution"],
    })

if not runs:
    sys.exit("no experiment runs in results/raw/ yet")

with open(os.path.join(OUT, "summary.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["run_id", "config", "concurrency", "total", "success", "errors",
                "error_pct", "rps", "mean", "stddev", "min", "p50", "p90", "p95",
                "p99", "max", "distribution"])
    for r in runs:
        w.writerow([r[k] for k in ("run_id", "config", "concurrency", "total",
                    "success", "errors", "error_pct", "rps", "mean", "stddev",
                    "min", "p50", "p90", "p95", "p99", "max")] +
                   [json.dumps(r["dist"])])

# ── median across repetitions ───────────────────────────────────────────────
groups = {}
for r in runs:
    groups.setdefault((r["config"], r["concurrency"]), []).append(r)

med_rows = []
for (cfg, conc), rs in sorted(groups.items()):
    med = lambda k: round(statistics.median(x[k] for x in rs), 2)
    dist = {}
    for r in rs:
        for b, n in r["dist"].items():
            dist[b] = dist.get(b, 0) + n
    tot_dist = sum(dist.values()) or 1
    dist_pct = {b: round(n / tot_dist * 100, 1) for b, n in sorted(dist.items())}
    med_rows.append({
        "config": cfg, "concurrency": conc, "reps": len(rs),
        "total": med("total"), "success": med("success"), "errors": med("errors"),
        "error_pct": med("error_pct"),
        "rps": med("rps"), "rps_min": min(x["rps"] for x in rs),
        "rps_max": max(x["rps"] for x in rs),
        "mean": med("mean"), "p50": med("p50"), "p90": med("p90"),
        "p95": med("p95"), "p99": med("p99"), "max": med("max"),
        "dist_pct": dist_pct,
        "run_ids": ",".join(x["run_id"] for x in rs),
    })

with open(os.path.join(OUT, "medians.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    hdr = ["config", "concurrency", "reps", "total", "success", "errors",
           "error_pct", "rps", "rps_min", "rps_max", "mean", "p50", "p90",
           "p95", "p99", "max", "dist_pct", "run_ids"]
    w.writerow(hdr)
    for m in med_rows:
        w.writerow([json.dumps(m[k]) if k == "dist_pct" else m[k] for k in hdr])

# ── the assignment's comparison table ───────────────────────────────────────
def speedup(conc):
    b = next((m for m in med_rows if m["config"] == "B" and m["concurrency"] == conc), None)
    c = next((m for m in med_rows if m["config"] == "C" and m["concurrency"] == conc), None)
    return round(c["rps"] / b["rps"], 2) if b and c and b["rps"] else "—"

lines = [
    "## Comparison table — LB with one backend (B) vs three backends (C)",
    "",
    "All values are the **median of 3 repetitions**; 60 s runs, first 10 s discarded.",
    "Distribution shows the share of requests each backend served.",
    "",
    "| Concurrency | Config | Total Req | Success | Errors | Err % | Throughput (req/s) "
    "| Mean (ms) | p50 | p90 | p95 | p99 | Max | Distribution sys2/3/4 (%) | Speedup C vs B |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
]
for m in sorted(med_rows, key=lambda m: (m["concurrency"], m["config"])):
    if m["config"] not in ("A", "B", "C"):
        continue
    d = "/".join(str(m["dist_pct"].get(k, 0)) for k in ("sys2", "sys3", "sys4"))
    sp = speedup(m["concurrency"]) if m["config"] == "C" else ""
    lines.append(
        f"| {m['concurrency']} | {m['config']} | {m['total']} | {m['success']} "
        f"| {m['errors']} | {m['error_pct']} | **{m['rps']}** | {m['mean']} "
        f"| {m['p50']} | {m['p90']} | {m['p95']} | {m['p99']} | {m['max']} | {d} | {sp} |")

os.makedirs(os.path.join(ROOT, "report"), exist_ok=True)
with open(os.path.join(ROOT, "report", "comparison_table.md"), "w") as fh:
    fh.write("\n".join(lines) + "\n")
print("wrote summary.csv, medians.csv, comparison_table.md "
      f"({len(runs)} runs, {len(med_rows)} groups)")

# ── charts ──────────────────────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib unavailable — charts skipped (re-run with the venv python)")
    sys.exit(0)

COLORS = {"A": "#888888", "B": "#d97706", "C": "#4f6df5"}
LABELS = {"A": "A — direct sys2", "B": "B — LB × 1 backend", "C": "C — LB × 3 backends"}

def series(cfg, key):
    pts = sorted([(m["concurrency"], m[key]) for m in med_rows if m["config"] == cfg])
    return [p[0] for p in pts], [p[1] for p in pts]

# 1. throughput vs concurrency
plt.figure(figsize=(7, 4.5))
for cfg in ("A", "B", "C"):
    x, y = series(cfg, "rps")
    if x:
        plt.plot(x, y, "o-", color=COLORS[cfg], label=LABELS[cfg])
plt.xscale("log"); plt.xlabel("concurrency (virtual users)")
plt.ylabel("throughput (req/s)"); plt.title("Throughput vs concurrency")
plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
plt.savefig(os.path.join(CHARTS, "throughput_vs_concurrency.png"), dpi=150)

# 2. p95 latency vs concurrency
plt.figure(figsize=(7, 4.5))
for cfg in ("B", "C"):
    x, y = series(cfg, "p95")
    if x:
        plt.plot(x, y, "o-", color=COLORS[cfg], label=LABELS[cfg])
plt.xscale("log"); plt.yscale("log"); plt.xlabel("concurrency")
plt.ylabel("p95 latency (ms)"); plt.title("p95 latency vs concurrency")
plt.legend(); plt.grid(alpha=.3, which="both"); plt.tight_layout()
plt.savefig(os.path.join(CHARTS, "p95_vs_concurrency.png"), dpi=150)

# 3. latency CDF at c=100 (full samples from raw records)
plt.figure(figsize=(7, 4.5))
for cfg in ("B", "C"):
    lat = []
    for path in glob.glob(os.path.join(RAW, f"{cfg}_c100_rep*.json")):
        with open(path) as fh:
            lat += [r["ms"] for r in json.load(fh)["records"] if r["status"] == 200]
    if lat:
        lat.sort()
        ys = [i / len(lat) for i in range(len(lat))]
        plt.plot(lat, ys, color=COLORS[cfg], label=LABELS[cfg])
plt.xscale("log"); plt.xlabel("latency (ms)"); plt.ylabel("CDF")
plt.title("Latency CDF at concurrency = 100")
plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
plt.savefig(os.path.join(CHARTS, "latency_cdf_c100.png"), dpi=150)

# 4. per-backend distribution for config C (stacked bars over concurrency)
cs = sorted({m["concurrency"] for m in med_rows if m["config"] == "C"})
if cs:
    plt.figure(figsize=(7, 4.5))
    bottoms = [0] * len(cs)
    for b, col in (("sys2", "#4f6df5"), ("sys3", "#7c94f8"), ("sys4", "#b3c0fb")):
        vals = []
        for c in cs:
            m = next(m for m in med_rows if m["config"] == "C" and m["concurrency"] == c)
            vals.append(m["dist_pct"].get(b, 0))
        plt.bar([str(c) for c in cs], vals, bottom=bottoms, label=b, color=col)
        bottoms = [x + v for x, v in zip(bottoms, vals)]
    plt.xlabel("concurrency"); plt.ylabel("share of requests (%)")
    plt.title("Per-backend distribution — config C (round robin)")
    plt.legend(); plt.tight_layout()
    plt.savefig(os.path.join(CHARTS, "backend_distribution_C.png"), dpi=150)

# 5. failover time-series (config D), if present
d_runs = glob.glob(os.path.join(RAW, "D_*.json"))
if d_runs:
    with open(d_runs[0]) as fh:
        data = json.load(fh)
    ts = data["summary"]["timeseries_5s"]
    xs = [int(k) for k in ts]; xs.sort()
    plt.figure(figsize=(7, 4.5))
    plt.plot(xs, [ts[str(x)]["requests"] / 5 for x in xs], "o-", color="#4f6df5", label="req/s")
    plt.plot(xs, [ts[str(x)]["errors"] / 5 for x in xs], "o-", color="#c62828", label="errors/s")
    kill_t = data["summary"].get("kill_at_s")
    if kill_t:
        plt.axvline(kill_t, color="#c62828", ls="--", alpha=.6)
        plt.text(kill_t, plt.ylim()[1] * .9, " backend killed", color="#c62828")
    plt.xlabel("time (s)"); plt.ylabel("per second")
    plt.title("Failover run — throughput while one backend dies")
    plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
    plt.savefig(os.path.join(CHARTS, "failover_timeseries.png"), dpi=150)

# 6. algorithm sweep (config E), if present
e_groups = sorted({m["config"] for m in med_rows if m["config"].startswith("E_")})
if e_groups:
    plt.figure(figsize=(7, 4.5))
    names = [g[2:] for g in e_groups]
    vals = [next(m["rps"] for m in med_rows if m["config"] == g) for g in e_groups]
    plt.bar(names, vals, color="#4f6df5")
    plt.ylabel("throughput (req/s) @ c=100")
    plt.title("Algorithm comparison — 3 backends, c=100")
    plt.xticks(rotation=15); plt.tight_layout()
    plt.savefig(os.path.join(CHARTS, "algorithm_sweep.png"), dpi=150)

print("charts written to results/charts/")
