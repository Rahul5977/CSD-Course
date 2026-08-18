# ADR 0001 — Layered architecture with a framework-free core

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

The rubric awards 3 marks for "layered architecture and separation of concerns",
evidenced by routers that contain no business logic. Beyond the marks, the
hydrology engine has to be unit-testable without a database, a network or an
HTTP client — a D8 flow-routing test that needs Postgres running is a test
nobody runs.

## Decision

Five layers, with dependencies pointing inwards only:

```
api  ->  schemas  ->  engines  ->  domain
 |          |            |
 +-> jobs ->+            +-> providers, repositories
```

- `domain/` — value objects, units, invariants. Imports no framework at all.
- `engines/` — hydrology, runoff, pond design. Pure functions over plain inputs;
  reaches the outside world only through Protocols passed in by the caller.
- `providers/`, `repositories/` — adapters to DEM sources, rainfall APIs, Postgres.
- `schemas/` — Pydantic wire contract, kept separate from `domain` so the HTTP
  shape can be versioned without disturbing the model.
- `api/` — routers. Validate, delegate once, map the result, translate errors.

`mypy --strict` is scoped to `app/domain` and `app/engines`.

## Consequences

A convention that is only written down decays. `tests/test_layering.py` enforces
this mechanically by parsing the AST of every module:

1. no framework import (`fastapi`, `sqlalchemy`, `httpx`, …) inside `domain` or `engines`;
2. no layer imports a layer further out than itself;
3. no handler in `api/` exceeds 25 statements — a crude but honest proxy for
   "contains no business logic". When it fails, the fix is to move the body into
   an engine, never to raise the limit.

Cost: two objects for the same concept (a domain `Catchment` and a
`CatchmentResponse`) and the mapping between them. Accepted, because the
alternative — returning ORM objects from routes — couples the wire format to the
database schema, and every later migration becomes a breaking API change.
