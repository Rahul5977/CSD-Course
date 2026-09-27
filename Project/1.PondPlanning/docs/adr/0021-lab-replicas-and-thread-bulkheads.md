# ADR 0021 — Lab deployment: shared-nothing replicas, thread-pool bulkheads, ip_hash balancing

**Status:** Accepted · 2026-09-27 · Phase P9

## Context

Phase 3 asks for a solution that is "fast and functional, with appropriate consideration for
stress, scaling, and system limitations within the four systems provided". The four lab VMs
are unprivileged containers (no Docker, no systemd, no root), so the reference 11-service
stack (ADR 0004, 0019) cannot run there. v1.0 ran one process per VM with the *inline* job
runner. The first load test on the lab (20 users, 90 s) showed:

- `POST /analyzeArea` blocking 11–21 s: the inline runner executes the job inside the request,
  breaking the `202`-and-poll contract and tying up a request thread per analysis;
- rainfall p95 43 s: ten users opening one village all missed the cache and called Open-Meteo.

The lbsys1 process also died silently twice during the project.

## Decisions

1. **`ThreadJobRunner`** — a third adapter behind the `JobRunner` port: two process-wide
   bounded pools, `interactive` (8) and `heavy` (2), mirroring the Celery queues. The POST
   returns `202` at once; `429 queue_saturated` when a pool's pending count reaches
   `POND_MAX_QUEUE_DEPTH`. The heavy pool is small on purpose: the hydrology loops are
   GIL-bound Python, so extra threads add waiting, not throughput.
2. **Single-flight cache misses** in the `Cached` rainfall decorator (per-key lock, re-check
   after acquiring).
3. **Shared-nothing replicas** on each VM (`infra/lab/run_replica.sh`, which is also the
   supervisor: it restarts uvicorn when it exits).
4. **nginx `ip_hash` load balancer** (user-space nginx already present on lbsys4,
   `infra/lab/nginx-lb.conf`): replicas keep villages and jobs in memory, so a client must keep
   reaching one replica; `max_fails`/`fail_timeout` remove a dead replica and
   `proxy_next_upstream` retries a failed connection on another.

## Result

Same 20-user test on one process: `POST /analyzeArea` p95 17 ms; area analysis p50 2 s, p95 4 s;
rainfall p95 63 ms; 154 area analyses in 90 s (`docs/figures/p9-locust-*.txt`).

## Alternatives rejected

- **Multiple uvicorn workers per VM** — memory state is per process, so a job created in one
  worker is invisible to the next request; it would need the shared stores the VM cannot run.
- **Round-robin balancing** — breaks the same way across replicas; `ip_hash` is the minimum
  that is correct. Its cost, stated: clients behind one NAT share a replica, and a
  failed-over user re-runs their analysis (~2 s).
- **Process pool for heavy jobs** — real CPU parallelism, but job state would have to cross
  process boundaries; replicas give the same parallelism with no new mechanism.

## Consequences

The Docker stack remains the reference for shared state and horizontal scaling of workers;
the lab shape trades state durability (a restart forgets analyses) for running at all on
the machines provided — the trade-off the report states.
