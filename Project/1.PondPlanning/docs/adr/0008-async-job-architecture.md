# ADR 0008 — Analysis routes return 202 and a poll URL

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

A catchment delineation takes roughly 10-25 seconds: read the COG, fill sinks,
route flow, accumulate, snap, traverse, vectorise. A full pond design chains
several of those.

## Decision

Every analysis route validates its request, enqueues a job, and returns `202`
with a job id and a `poll_url`. The client polls `GET /api/v1/jobs/{id}` for
`status`, `progress` and `stage`, then fetches the result.

## Why

1. **Holding a request open for 25 seconds is fragile.** Default proxy and
   gateway timeouts sit at 30-60 s. A pipeline that grows slightly, or a cold
   cache, turns into a 504 with no diagnostic.
2. **The user needs progress.** A spinner with no information is
   indistinguishable from a hang. `stage` ("filling sinks", "tracing upstream
   cells") is why the field exists in `JobStatus` from the first commit.
3. **Failure becomes a value, not an exception.** A failed job is a row with an
   error, retryable and auditable, rather than a stack trace in a log.
4. **It is directly graded** — 3 marks for the async job architecture, with
   "real percentages" named as the evidence.

## Alternatives rejected

- **Synchronous responses.** Simpler until the first timeout, then a rewrite of
  every client.
- **WebSockets/SSE for progress.** More responsive, but adds a transport to
  defend in the viva and a reconnection story to write, for a UI that updates
  once a second at most.

## Consequences

The contract is fixed in P0 even though the worker arrives in P1: `JobAccepted`,
`JobStatus` and `/jobs/*` all exist now, so the frontend polls correctly from the
first screen it builds. The `jobs` table carries a `CHECK` constraint on status,
so a crashed worker cannot leave a row in a state the poll route cannot read.
