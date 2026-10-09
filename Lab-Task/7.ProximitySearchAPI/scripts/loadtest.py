#!/usr/bin/env python3
"""Closed-loop HTTP load test against a running API.

    .venv/bin/python scripts/loadtest.py http://127.0.0.1:3000 --requests 5000 --concurrency 32
"""
import argparse
import asyncio
import random
import statistics
import time

import httpx

CATS = ["bank", "cafe", "hospital", "park", "pharmacy", "restaurant", "school", "store"]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--requests", type=int, default=5000)
    ap.add_argument("--concurrency", type=int, default=32)
    a = ap.parse_args()
    rng = random.Random(9)
    queries = [{"lat": round(rng.random(), 4), "long": round(rng.random(), 4), "cat": rng.choice(CATS),
                "rad": round(rng.uniform(0.1, 0.4), 3)} for _ in range(a.requests)]
    lat, errors, it = [], 0, iter(queries)

    async def worker(client):
        nonlocal errors
        for q in it:
            t = time.perf_counter()
            r = await client.get("/search/", params=q)
            lat.append((time.perf_counter() - t) * 1e3)
            if r.status_code != 200 or len(r.json()["ids"]) != 10:
                errors += 1

    limits = httpx.Limits(max_connections=a.concurrency)
    async with httpx.AsyncClient(base_url=a.base, limits=limits, timeout=10) as client:
        t0 = time.perf_counter()
        await asyncio.gather(*(worker(client) for _ in range(a.concurrency)))
        wall = time.perf_counter() - t0
    lat.sort()
    p = lambda q: lat[int(q * (len(lat) - 1))]
    print(f"requests={len(lat)} concurrency={a.concurrency} errors={errors} wall={wall:.2f}s "
          f"throughput={len(lat) / wall:.0f} req/s p50={p(.5):.1f}ms p95={p(.95):.1f}ms p99={p(.99):.1f}ms "
          f"mean={statistics.fmean(lat):.1f}ms")


if __name__ == "__main__":
    asyncio.run(main())
