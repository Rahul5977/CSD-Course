#!/usr/bin/env python3
"""
loadgen.py — custom HTTP load generator for the messaging app (Assignment 5).

Runs on the local Mac and drives the load balancer (or a single backend for
the baseline). Pure Python 3 standard library.

Two modes:
  closed-loop (default): N virtual users, each in a request->response loop
                         with optional think time. Load adapts to latency.
  open-loop  (--rate R): requests arrive at a fixed Poisson rate regardless
                         of how slow responses are — exposes queueing delay.

Realistic request mix (per virtual user, weighted):
  10%  POST /api/login      (re-login, exercises auth + state service)
  55%  GET  /api/messages   (fetch)
  30%  POST /api/messages   (send)
   5%  GET  /health
Each virtual user registers its own account + session cookie during setup
(setup traffic is excluded from measurements).

Per request we record: start time, latency ms, HTTP status, error class and
the X-Backend-Id header — the last one is the per-backend distribution proof.
The first --warmup seconds are discarded from statistics. Percentiles are
computed from the full recorded sample array, never a running approximation.

Output: results/raw/<run_id>.json  +  a console summary.

Example:
  python3 loadgen.py --url http://10.1.75.53:3269 --concurrency 50 \
      --duration 60 --warmup 10 --run-id C_c50_rep1
"""

import argparse
import http.client
import json
import os
import random
import socket
import ssl
import sys
import threading
import time
from urllib.parse import urlparse

MIX = [("login", 10), ("fetch", 55), ("send", 30), ("health", 5)]
MIX_EXPANDED = [name for name, w in MIX for _ in range(w)]

WORDS = ("alpha bravo charlie delta echo foxtrot golf hotel india juliet "
         "kilo lima mike november oscar papa quebec romeo sierra tango").split()


class VUser:
    """One virtual user: own account, own session cookie, own connection."""

    def __init__(self, idx, base, run_id):
        self.idx = idx
        self.base = urlparse(base)
        # Stable name across runs: register once ever, login thereafter.
        # (Registration is scrypt-expensive on the 1-core lab containers.)
        self.name = f"lg_{idx}"
        self.password = "loadgen-pass-12345"
        self.cookie = None
        self.conn = None
        self.room = "loadtest"

    def connect(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = http.client.HTTPConnection(
            self.base.hostname, self.base.port or 80, timeout=10)

    def request(self, method, path, body=None):
        """One HTTP request over the persistent connection. Returns
        (status, headers, body_bytes) and reconnects on connection death."""
        payload = json.dumps(body).encode() if body is not None else None
        headers = {}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.cookie:
            headers["Cookie"] = self.cookie
        try:
            self.conn.request(method, path, payload, headers)
            resp = self.conn.getresponse()
            data = resp.read()
        except (http.client.HTTPException, OSError):
            self.connect()          # one silent reconnect, then it counts
            self.conn.request(method, path, payload, headers)
            resp = self.conn.getresponse()
            data = resp.read()
        sc = resp.getheader("Set-Cookie")
        if sc:
            self.cookie = sc.split(";")[0]
        return resp.status, resp, data

    def setup(self):
        """Register (or login) once. Not measured. scrypt costs ~100 ms of a
        1-core backend, so callers MUST stagger setup (see setup phase)."""
        self.connect()
        self.conn.timeout = 30
        st, _, _ = self.request("POST", "/api/register",
                                {"username": self.name, "password": self.password})
        if st == 409:
            st, _, _ = self.request("POST", "/api/login",
                                    {"username": self.name, "password": self.password})
        if st != 200:
            raise RuntimeError(f"user {self.name} setup failed: HTTP {st}")
        self.request("POST", "/api/rooms", {"id": self.room})
        self.conn.timeout = 10

    def one(self, kind):
        """Execute one request of the mix; returns (status, backend_id)."""
        if kind == "login":
            st, resp, _ = self.request("POST", "/api/login",
                                       {"username": self.name, "password": self.password})
        elif kind == "fetch":
            since = random.randint(0, 50)
            st, resp, _ = self.request("GET", f"/api/messages?room={self.room}&since={since}")
        elif kind == "send":
            text = " ".join(random.choices(WORDS, k=random.randint(3, 12)))
            st, resp, _ = self.request("POST", "/api/messages",
                                       {"room": self.room, "text": text})
        else:
            st, resp, _ = self.request("GET", "/health")
        return st, resp.getheader("X-Backend-Id") or "?"


def percentile(sorted_arr, p):
    if not sorted_arr:
        return 0.0
    idx = min(len(sorted_arr) - 1, int(p / 100 * len(sorted_arr)))
    return sorted_arr[idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--duration", type=int, default=60)
    ap.add_argument("--warmup", type=int, default=10,
                    help="seconds discarded from statistics")
    ap.add_argument("--rate", type=float, default=0,
                    help="open-loop arrival rate req/s (0 = closed loop)")
    ap.add_argument("--think", type=float, default=0,
                    help="closed-loop think time seconds between requests")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out-dir", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "results", "raw"))
    args = ap.parse_args()
    run_id = args.run_id or f"run_{int(time.time())}"

    print(f"[loadgen] {run_id}: target={args.url} c={args.concurrency} "
          f"dur={args.duration}s warmup={args.warmup}s "
          f"mode={'open@'+str(args.rate)+'rps' if args.rate else 'closed'}")

    # ── setup phase (not measured) ──────────────────────────────────────────
    users = [VUser(i, args.url, run_id) for i in range(args.concurrency)]
    setup_errors = 0
    # Stagger setup: at most 8 concurrent registrations/logins, so the scrypt
    # cost doesn't saturate a 1-core backend and trip its health checks.
    sem = threading.Semaphore(8)
    def setup_worker(u):
        nonlocal setup_errors
        with sem:
            for attempt in (1, 2):
                try:
                    u.setup()
                    return
                except Exception as e:
                    if attempt == 2:
                        setup_errors += 1
                        print(f"[loadgen] setup failed for {u.name}: {e}", file=sys.stderr)
                    else:
                        time.sleep(1)
    threads = [threading.Thread(target=setup_worker, args=(u,)) for u in users]
    for t in threads: t.start()
    for t in threads: t.join()
    if setup_errors > args.concurrency // 4:
        print("[loadgen] too many setup failures, aborting", file=sys.stderr)
        sys.exit(1)
    print(f"[loadgen] {len(users) - setup_errors}/{len(users)} users ready")

    # ── measurement phase ───────────────────────────────────────────────────
    records = []                 # (t_start_rel, latency_ms, status, backend, err)
    rec_lock = threading.Lock()
    stop = threading.Event()
    t_begin = time.time()

    def record(t0, ms, status, backend, err):
        with rec_lock:
            records.append((round(t0 - t_begin, 3), round(ms, 2), status, backend, err))

    def closed_worker(u):
        while not stop.is_set():
            kind = random.choice(MIX_EXPANDED)
            t0 = time.time()
            try:
                st, backend = u.one(kind)
                record(t0, (time.time() - t0) * 1000, st, backend, "")
            except Exception as e:
                record(t0, (time.time() - t0) * 1000, 0, "?",
                       type(e).__name__)
                try:
                    u.connect()
                except Exception:
                    time.sleep(0.5)
            if args.think:
                time.sleep(args.think)

    def open_loop_dispatcher():
        """Poisson arrivals at --rate; each request runs on its own thread
        drawn from the user pool round-robin."""
        i = 0
        while not stop.is_set():
            time.sleep(random.expovariate(args.rate))
            u = users[i % len(users)]
            i += 1
            kind = random.choice(MIX_EXPANDED)
            def fire(u=u, kind=kind):
                t0 = time.time()
                try:
                    st, backend = u.one(kind)
                    record(t0, (time.time() - t0) * 1000, st, backend, "")
                except Exception as e:
                    record(t0, (time.time() - t0) * 1000, 0, "?", type(e).__name__)
            threading.Thread(target=fire, daemon=True).start()

    if args.rate:
        workers = [threading.Thread(target=open_loop_dispatcher, daemon=True)]
    else:
        workers = [threading.Thread(target=closed_worker, args=(u,), daemon=True)
                   for u in users]
    for w in workers:
        w.start()

    # live console ticker
    t_end = t_begin + args.duration
    while time.time() < t_end:
        time.sleep(5)
        with rec_lock:
            n = len(records)
        print(f"[loadgen] t+{time.time()-t_begin:4.0f}s  {n} requests so far")
    stop.set()
    time.sleep(2)                # let in-flight requests finish recording

    # ── statistics (warm-up discarded, full-sample percentiles) ─────────────
    sample = [r for r in records if r[0] >= args.warmup]
    lat = sorted(r[1] for r in sample if r[2] == 200)
    okc = sum(1 for r in sample if r[2] == 200)
    errc = len(sample) - okc
    span = args.duration - args.warmup
    dist = {}
    errors_by_class = {}
    for r in sample:
        dist[r[3]] = dist.get(r[3], 0) + 1
        if r[2] != 200:
            key = r[4] or f"HTTP{r[2]}"
            errors_by_class[key] = errors_by_class.get(key, 0) + 1
    mean = sum(lat) / len(lat) if lat else 0
    stddev = (sum((x - mean) ** 2 for x in lat) / len(lat)) ** 0.5 if lat else 0

    # 5-second time-series buckets for charts
    buckets = {}
    for r in sample:
        b = int(r[0] // 5) * 5
        buckets.setdefault(b, [0, 0])
        buckets[b][0] += 1
        if r[2] != 200:
            buckets[b][1] += 1

    summary = {
        "run_id": run_id, "url": args.url, "concurrency": args.concurrency,
        "duration_s": args.duration, "warmup_s": args.warmup,
        "mode": "open" if args.rate else "closed", "rate": args.rate,
        "started_at": t_begin,
        "total_requests": len(sample), "success": okc, "errors": errc,
        "error_rate_pct": round(errc / len(sample) * 100, 3) if sample else 0,
        "errors_by_class": errors_by_class,
        "throughput_rps": round(okc / span, 2) if span else 0,
        "latency_ms": {
            "mean": round(mean, 2), "stddev": round(stddev, 2),
            "min": round(lat[0], 2) if lat else 0,
            "p50": round(percentile(lat, 50), 2),
            "p90": round(percentile(lat, 90), 2),
            "p95": round(percentile(lat, 95), 2),
            "p99": round(percentile(lat, 99), 2),
            "max": round(lat[-1], 2) if lat else 0,
        },
        "backend_distribution": dist,
        "timeseries_5s": {str(k): {"requests": v[0], "errors": v[1]}
                          for k, v in sorted(buckets.items())},
    }

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"{run_id}.json")
    with open(out_path, "w") as fh:
        json.dump({"summary": summary,
                   "records": [{"t": r[0], "ms": r[1], "status": r[2],
                                "backend": r[3], "err": r[4]} for r in sample]},
                  fh)
    print(json.dumps(summary, indent=2))
    print(f"[loadgen] wrote {out_path}")


if __name__ == "__main__":
    main()
