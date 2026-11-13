#!/usr/bin/env python3
"""Summarise FIO JSON outputs (stdlib only).

Reads  results/raw/*.json  (main experiments, 3 reps) and results/supp/*.json
Writes results/per_run.csv, results/summary.csv, results/supp_summary.csv,
       report/data/*.dat (pgfplots) and report/tables/*.tex (table bodies).

Usage: python3 -I scripts/analyze.py <lab-folder>
"""
import csv
import glob
import json
import os
import re
import statistics as st
import sys

LAB = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(LAB, "results")
DATA = os.path.join(LAB, "report", "data")
TABLES = os.path.join(LAB, "report", "tables")
os.makedirs(DATA, exist_ok=True)
os.makedirs(TABLES, exist_ok=True)

CASES = ["A_randread_4k", "B_randrw70_4k", "C_randrw30_8k", "D_seqread_256k"]
LABEL = {"A_randread_4k": "A", "B_randrw70_4k": "B", "C_randrw30_8k": "C", "D_seqread_256k": "D"}
QDS = [1, 8, 32]


def pct(d, p):
    v = d.get("clat_ns", {}).get("percentile", {}).get(f"{p:.6f}")
    return v / 1000.0 if v is not None else None


def direction(j, key):
    d = j[key]
    if d["total_ios"] == 0:
        return None
    return {
        "ios": d["total_ios"],
        "iops": d["iops"],
        "bw_mib": d["bw_bytes"] / 2**20,
        "lat_us": d["lat_ns"]["mean"] / 1000.0,
        "slat_us": d["slat_ns"]["mean"] / 1000.0,
        "clat_us": d["clat_ns"]["mean"] / 1000.0,
        "p50": pct(d, 50), "p95": pct(d, 95), "p99": pct(d, 99), "p999": pct(d, 99.9),
        "max_us": d["lat_ns"]["max"] / 1000.0,
    }


def parse(path):
    doc = json.load(open(path))
    j = doc["jobs"][0]
    r, w = direction(j, "read"), direction(j, "write")
    parts = [x for x in (r, w) if x]
    ios = sum(x["ios"] for x in parts)
    lvl = j.get("iodepth_level", {})
    modal = max(lvl, key=lambda k: lvl[k]) if lvl else ""
    util = doc.get("disk_util", [{}])
    return {
        "file": os.path.basename(path),
        "fio": doc.get("fio version", ""),
        "iops": sum(x["iops"] for x in parts),
        "bw_mib": sum(x["bw_mib"] for x in parts),
        "lat_us": sum(x["lat_us"] * x["ios"] for x in parts) / ios,
        "r": r, "w": w,
        "depth_modal": modal, "depth_modal_pct": lvl.get(modal, 0.0),
        "cpu": j["usr_cpu"] + j["sys_cpu"],
        "util": util[0].get("util", 0.0) if util else 0.0,
        "runtime_s": j["job_runtime"] / 1000.0,
    }


def g(x, k):
    return x[k] if x else None


def mean_sd(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    return st.mean(vals), (st.stdev(vals) if len(vals) > 1 else 0.0)


# ---------------------------------------------------------------- main runs
runs = {}
per_run_rows = []
for path in sorted(glob.glob(os.path.join(RES, "raw", "*.json"))):
    m = re.match(r"(.+)_qd(\d+)_r(\d+)\.json", os.path.basename(path))
    case, qd, rep = m.group(1), int(m.group(2)), int(m.group(3))
    p = parse(path)
    runs.setdefault((case, qd), []).append(p)
    per_run_rows.append([case, qd, rep, round(p["iops"], 1), round(p["bw_mib"], 2), round(p["lat_us"], 2),
                         g(p["r"], "p95"), g(p["r"], "p99"), g(p["w"], "p95"), g(p["w"], "p99"),
                         p["depth_modal"], round(p["depth_modal_pct"], 1), round(p["cpu"], 1), p["util"]])

with open(os.path.join(RES, "per_run.csv"), "w", newline="") as f:
    cw = csv.writer(f)
    cw.writerow(["case", "qd", "rep", "iops", "bw_mib_s", "avg_lat_us", "read_p95_us", "read_p99_us",
                 "write_p95_us", "write_p99_us", "achieved_depth_bucket", "depth_bucket_pct", "cpu_pct", "disk_util_pct"])
    cw.writerows(per_run_rows)

S = {}
for (case, qd), lst in runs.items():
    s = {"n": len(lst)}
    for k in ("iops", "bw_mib", "lat_us", "cpu", "util"):
        s[k] = mean_sd([x[k] for x in lst])
    for d in ("r", "w"):
        for k in ("iops", "lat_us", "p50", "p95", "p99", "p999", "max_us"):
            s[f"{d}_{k}"] = mean_sd([g(x[d], k) for x in lst])
    s["depth"] = lst[0]["depth_modal"]
    s["depth_pct"] = st.mean(x["depth_modal_pct"] for x in lst)
    S[(case, qd)] = s

hdr = ["case", "qd", "n", "iops_mean", "iops_sd", "iops_cv_pct", "bw_mib_mean", "bw_mib_sd", "avg_lat_us_mean",
       "read_p95_us", "read_p99_us", "write_p95_us", "write_p99_us", "read_p999_us", "write_p999_us",
       "achieved_depth", "cpu_pct", "disk_util_pct"]
with open(os.path.join(RES, "summary.csv"), "w", newline="") as f:
    cw = csv.writer(f)
    cw.writerow(hdr)
    for c in CASES:
        for qd in QDS:
            s = S.get((c, qd))
            if not s:
                continue
            r2 = lambda t: None if t[0] is None else round(t[0], 1)
            cw.writerow([c, qd, s["n"], round(s["iops"][0], 1), round(s["iops"][1], 1),
                         round(100 * s["iops"][1] / s["iops"][0], 2), round(s["bw_mib"][0], 2), round(s["bw_mib"][1], 2),
                         round(s["lat_us"][0], 2), r2(s["r_p95"]), r2(s["r_p99"]), r2(s["w_p95"]), r2(s["w_p99"]),
                         r2(s["r_p999"]), r2(s["w_p999"]), s["depth"], round(s["cpu"][0], 1), round(s["util"][0], 1)])


# ------------------------------------------------------------- LaTeX tables
def fk(v):
    if v is None:
        return "--"
    if v >= 1e5:
        return f"{v/1000:.0f}k"
    if v >= 1e4:
        return f"{v/1000:.1f}k"
    return f"{v:,.0f}"


def fl(v):
    if v is None:
        return "--"
    return f"{v:,.0f}" if v >= 100 else f"{v:.1f}"


rows = []
for c in CASES:
    for i, qd in enumerate(QDS):
        s = S.get((c, qd))
        if not s:
            continue
        cv = 100 * s["iops"][1] / s["iops"][0]
        p95 = fl(s["r_p95"][0]) if s["w_p95"][0] is None else f"{fl(s['r_p95'][0])} / {fl(s['w_p95'][0])}"
        p99 = fl(s["r_p99"][0]) if s["w_p99"][0] is None else f"{fl(s['r_p99'][0])} / {fl(s['w_p99'][0])}"
        lead = f"\\multirow{{3}}{{*}}{{\\textbf{{{LABEL[c]}}}}}" if i == 0 else ""
        rows.append(f"{lead} & {qd} & {fk(s['iops'][0])} & {cv:.1f} & {s['bw_mib'][0]:,.1f} & "
                    f"{fl(s['lat_us'][0])} & {p95} & {p99} & {s['depth']} \\\\")
    rows.append("\\midrule")
rows = rows[:-1]
open(os.path.join(TABLES, "main.tex"), "w").write("\n".join(rows) + "\n")

# scaling table: speed-up vs QD1 and latency growth
rows = []
for c in CASES:
    b, m, t = S[(c, 1)], S[(c, 8)], S[(c, 32)]
    rows.append(f"{LABEL[c]} & {m['iops'][0]/b['iops'][0]:.2f}$\\times$ & {t['iops'][0]/b['iops'][0]:.2f}$\\times$ & "
                f"{t['iops'][0]/m['iops'][0]:.2f}$\\times$ & {m['lat_us'][0]/b['lat_us'][0]:.1f}$\\times$ & "
                f"{t['lat_us'][0]/b['lat_us'][0]:.1f}$\\times$ \\\\")
open(os.path.join(TABLES, "scaling.tex"), "w").write("\n".join(rows) + "\n")

# per-direction table for mixed workloads
rows = []
for c in ("B_randrw70_4k", "C_randrw30_8k"):
    for qd in QDS:
        s = S[(c, qd)]
        rows.append(f"{LABEL[c]} & {qd} & {fk(s['r_iops'][0])} & {fk(s['w_iops'][0])} & {fl(s['r_lat_us'][0])} & "
                    f"{fl(s['w_lat_us'][0])} & {fl(s['r_p99'][0])} & {fl(s['w_p99'][0])} & "
                    f"{fl(s['r_p999'][0])} & {fl(s['w_p999'][0])} \\\\")
    rows.append("\\midrule")
open(os.path.join(TABLES, "mixed.tex"), "w").write("\n".join(rows[:-1]) + "\n")

# ------------------------------------------------------------ plot data
for c in CASES:
    with open(os.path.join(DATA, f"{LABEL[c]}.dat"), "w") as f:
        f.write("qd iops iops_sd bw bw_sd lat rp95 rp99 wp99 worstp99\n")
        for qd in QDS:
            s = S[(c, qd)]
            wp = s["w_p99"][0] if s["w_p99"][0] is not None else float("nan")
            worst = max(v for v in (s["r_p99"][0], s["w_p99"][0]) if v is not None)
            f.write(f"{qd} {s['iops'][0]:.1f} {s['iops'][1]:.1f} {s['bw_mib'][0]:.2f} {s['bw_mib'][1]:.2f} "
                    f"{s['lat_us'][0]:.2f} {s['r_p95'][0]:.2f} {s['r_p99'][0]:.2f} {wp:.2f} {worst:.2f}\n")

# ------------------------------------------------------------ supplementary
supp_rows = []
wal = []
for path in sorted(glob.glob(os.path.join(RES, "supp", "*.json"))):
    if json.load(open(path))["jobs"][0]["error"]:
        print("skipping failed run:", os.path.basename(path))
        continue
    p = parse(path)
    if os.path.basename(path).startswith("E_wal"):
        wal.append(p)
        continue
    supp_rows.append((os.path.basename(path)[:-5], p))
with open(os.path.join(RES, "supp_summary.csv"), "w", newline="") as f:
    cw = csv.writer(f)
    cw.writerow(["run", "iops", "bw_mib_s", "avg_lat_us", "read_p50_us", "read_p99_us", "achieved_depth", "cpu_pct", "disk_util_pct"])
    for name, p in supp_rows:
        cw.writerow([name, round(p["iops"], 1), round(p["bw_mib"], 2), round(p["lat_us"], 2),
                     g(p["r"], "p50"), g(p["r"], "p99"), p["depth_modal"], round(p["cpu"], 1), p["util"]])

for c in ("A_randread_4k", "D_seqread_256k"):
    pts = []
    for name, p in supp_rows:
        m = re.match(rf"sweep_{c}_qd(\d+)$", name)
        if m:
            pts.append((int(m.group(1)), p))
    pts.sort()
    if pts:
        with open(os.path.join(DATA, f"sweep_{LABEL[c]}.dat"), "w") as f:
            f.write("qd iops bw lat p99\n")
            for qd, p in pts:
                f.write(f"{qd} {p['iops']:.1f} {p['bw_mib']:.2f} {p['lat_us']:.2f} {p['r']['p99']:.2f}\n")

sp = dict(supp_rows)
rows = []
def srow(label, p, note):
    return (f"{label} & {fk(p['iops'])} & {p['bw_mib']:,.1f} & {fl(p['lat_us'])} & {fl(p['r']['p50'])} & "
            f"{fl(p['r']['p99'])} & {note} \\\\")
if (("A_randread_4k", 1) in S) and "size8g_A_qd1" in sp:
    for qd in (1, 32):
        base = runs[("A_randread_4k", qd)][0]
        rows.append(srow(f"A, QD{qd}, 1 GiB, libaio (rep 1)", base, "main run"))
        rows.append(srow(f"A, QD{qd}, 8 GiB, libaio", sp[f"size8g_A_qd{qd}"], "working set $>$ VM RAM"))
    if "engine_iouring_A_qd32" in sp:
        rows.append(srow("A, QD32, 1 GiB, io\\_uring", sp["engine_iouring_A_qd32"], "engine cross-check"))
open(os.path.join(TABLES, "supp.tex"), "w").write("\n".join(rows) + "\n")

# ------------------------------------------------- 8 GiB matrix vs 1 GiB means
B8 = {}
for name, p in supp_rows:
    m = re.match(r"big8g_(.+)_qd(\d+)$", name)
    if m:
        B8[(m.group(1), int(m.group(2)))] = p
if B8:
    rows = []
    for c in CASES:
        for i, qd in enumerate(QDS):
            s, b = S[(c, qd)], B8.get((c, qd))
            if not b:
                continue
            bp99 = max(v for v in (g(b["r"], "p99"), g(b["w"], "p99")) if v is not None)
            sp99 = max(v for v in (s["r_p99"][0], s["w_p99"][0]) if v is not None)
            lead = f"\\multirow{{3}}{{*}}{{\\textbf{{{LABEL[c]}}}}}" if i == 0 else ""
            rows.append(f"{lead} & {qd} & {fk(s['iops'][0])} & {fk(b['iops'])} & {s['iops'][0]/b['iops']:.1f}$\\times$ & "
                        f"{s['bw_mib'][0]:,.0f} & {b['bw_mib']:,.0f} & {fl(s['lat_us'][0])} & {fl(b['lat_us'])} & "
                        f"{fl(sp99)} & {fl(bp99)} \\\\")
        rows.append("\\midrule")
    open(os.path.join(TABLES, "big.tex"), "w").write("\n".join(rows[:-1]) + "\n")
    for c in CASES:
        with open(os.path.join(DATA, f"{LABEL[c]}_8g.dat"), "w") as f:
            f.write("qd iops bw lat worstp99\n")
            for qd in QDS:
                b = B8[(c, qd)]
                worst = max(v for v in (g(b["r"], "p99"), g(b["w"], "p99")) if v is not None)
                f.write(f"{qd} {b['iops']:.1f} {b['bw_mib']:.2f} {b['lat_us']:.2f} {worst:.2f}\n")
    for c in CASES:
        for qd in QDS:
            b = B8[(c, qd)]
            print(f"8g {LABEL[c]} qd{qd:>2}: iops {b['iops']:>8.0f} bw {b['bw_mib']:8.1f} lat {b['lat_us']:7.1f} "
                  f"rP99 {g(b['r'],'p99')} wP99 {g(b['w'],'p99')} depth {b['depth_modal']} util {b['util']}")

# ------------------------------------------------- per-repetition IOPS (cache warming)
rows = []
for c in CASES:
    for qd in QDS:
        lst = runs[(c, qd)]
        reps = sorted((int(re.search(r"_r(\d+)", x["file"]).group(1)), x) for x in lst)
        v = [x["iops"] for _, x in reps]
        rows.append(f"{LABEL[c]} & {qd} & " + " & ".join(fk(x) for x in v) +
                    f" & {v[-1]/v[0]:.2f}$\\times$ & {100*st.stdev(v)/st.mean(v):.0f}\\% \\\\")
open(os.path.join(TABLES, "reps.tex"), "w").write("\n".join(rows) + "\n")

# case E (WAL-style sync appends): write-only, fdatasync after each 8 KiB write
if wal:
    sync = []
    for path in sorted(glob.glob(os.path.join(RES, "supp", "E_wal_r*.json"))):
        j = json.load(open(path))["jobs"][0]
        s_ = j.get("sync", {})
        sync.append({"mean": s_.get("lat_ns", {}).get("mean", 0) / 1000.0,
                     "p99": s_.get("lat_ns", {}).get("percentile", {}).get("99.000000", 0) / 1000.0})
    E = {k: mean_sd([x[k] for x in wal]) for k in ("iops", "bw_mib")}
    E["w_lat"] = mean_sd([x["w"]["lat_us"] for x in wal])
    E["w_p99"] = mean_sd([x["w"]["p99"] for x in wal])
    E["sync_mean"] = mean_sd([x["mean"] for x in sync])
    E["sync_p99"] = mean_sd([x["p99"] for x in sync])
    with open(os.path.join(RES, "supp_summary.csv"), "a", newline="") as f:
        csv.writer(f).writerow(["E_wal_mean_of_3", round(E["iops"][0], 1), round(E["bw_mib"][0], 2),
                                round(E["w_lat"][0], 2), "", round(E["w_p99"][0], 1), "1", "", ""])
    open(os.path.join(TABLES, "wal.tex"), "w").write(
        f"E & {E['iops'][0]:,.0f} $\\pm$ {E['iops'][1]:,.0f} & {E['bw_mib'][0]:.1f} & {fl(E['w_lat'][0])} & "
        f"{fl(E['w_p99'][0])} & {fl(E['sync_mean'][0])} & {fl(E['sync_p99'][0])} & "
        f"{1e6/(E['iops'][0]):,.0f} \\\\\n")
    print(f"E wal: iops {E['iops'][0]:.0f}±{E['iops'][1]:.0f} bw {E['bw_mib'][0]:.1f} write lat {E['w_lat'][0]:.1f} "
          f"wP99 {E['w_p99'][0]:.1f} sync mean {E['sync_mean'][0]:.1f} sync p99 {E['sync_p99'][0]:.1f}")

print(f"main cells: {len(S)} (runs: {sum(len(v) for v in runs.values())}), supplementary runs: {len(supp_rows)}")
for c in CASES:
    for qd in QDS:
        s = S.get((c, qd))
        if s:
            print(f"{LABEL[c]} qd{qd:>2}: iops {s['iops'][0]:>9.0f} ±{100*s['iops'][1]/s['iops'][0]:4.1f}%  "
                  f"bw {s['bw_mib'][0]:8.1f} MiB/s  lat {s['lat_us'][0]:7.1f}us  "
                  f"rP99 {s['r_p99'][0]}  wP99 {s['w_p99'][0]}  depth {s['depth']} ({s['depth_pct']:.0f}%)  "
                  f"cpu {s['cpu'][0]:.0f}%  util {s['util'][0]:.0f}%")
for name, p in supp_rows:
    print(f"{name:32s} iops {p['iops']:>9.0f} bw {p['bw_mib']:8.1f} lat {p['lat_us']:7.1f} p50 {p['r']['p50']} p99 {p['r']['p99']}")
