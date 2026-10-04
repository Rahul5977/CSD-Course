# ADR 0005 — FastAPI rather than Flask

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

`docs/assignment/Assignment.pdf` suggests "Python, Flask or FastAPI". Deviating from a
suggested stack without saying why loses marks; deviating with a reason earns
them. This ADR is one row of the stack reconciliation table the report needs.

## Decision

FastAPI.

## Why

1. **The OpenAPI document is generated from the code.** API documentation is
   worth 2 marks and is otherwise a hand-maintained file that drifts the first
   week. With FastAPI the schema *is* the code: `app/schemas/` produces
   `/openapi.json` and a browsable `/docs` with no extra work.
2. **Pydantic validation at the boundary.** Every request is parsed into a typed
   model before a handler runs, so "latitude 200" is rejected by the contract
   rather than by a geometry library ten frames deeper.
3. **`202` + polling is native.** The async job architecture is worth 3 marks
   and is on the never-cut list; FastAPI's background/ASGI model fits it.
4. **Typed handlers feed `mypy --strict`.** Flask handlers are untyped by
   default, which would weaken the type-checking evidence for Code Quality.

## Alternatives rejected

- **Flask.** Equally capable of serving these routes, but the OpenAPI document,
  the request validation and the response typing all become dependencies
  (flask-smorest, marshmallow) or hand-written code.
- **Django/DRF.** Brings an ORM, admin and auth we would use a fraction of; the
  geoprocessing is the hard part here, not the CRUD.

## Consequences

FastAPI runs synchronous handlers in a threadpool, which is exactly what ADR 0003
relies on. The `/docs` page is also the demo surface: it is where an evaluator
sees every endpoint without a frontend.
