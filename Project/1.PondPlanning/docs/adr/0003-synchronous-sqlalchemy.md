# ADR 0003 — Synchronous SQLAlchemy 2.0 on psycopg3

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

FastAPI is an async framework, so the reflexive choice is async SQLAlchemy with
asyncpg. Whether that is the *right* choice depends on where this system spends
its time.

It does not spend it in the database. The expensive operations are raster
processing — sink filling, D8 flow routing, flow accumulation over a DEM — which
take tens of seconds and run in a Celery worker, not in the request path.
Requests themselves do small, indexed reads and writes.

## Decision

Synchronous SQLAlchemy 2.0 with the psycopg3 driver. Route handlers that touch
the database are declared `def`, not `async def`, so FastAPI runs them in its
threadpool.

## Alternatives rejected

**Async SQLAlchemy + asyncpg.** Rejected on three grounds:

1. No measurable benefit at this concurrency. The bottleneck is the worker pool,
   not connection multiplexing.
2. It introduces a bug class that is easy to write and hard to see: one
   accidental blocking call inside an `async def` handler stalls the whole event
   loop, and it presents as "the app is sometimes slow" rather than as an error.
3. The explainability requirement. Every library must be justifiable live. "We
   used the sync driver because the heavy work is in the worker" is a complete
   answer; defending an async session lifecycle is a much larger surface for no
   benefit this project can measure.

## Consequences

If a later phase adds a genuinely I/O-bound, high-fan-out route, it can adopt an
async engine alongside this one — the repository Protocols in `app/repositories`
are the seam. Until then this stays the simpler system.
