# ADR 0006 — PostGIS rather than MongoDB

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

The assignment suggests "MongoDB/PostgreSQL". The data here is overwhelmingly
spatial: village boundaries, catchment polygons, stream networks, parcels,
candidate sites. The question is which store makes spatial queries cheap.

## Decision

PostgreSQL with the PostGIS extension.

## Why

1. **Spatial predicates in the database.** `ST_Intersects`, `ST_Area`,
   `ST_Buffer`, `ST_Transform` run next to the data. FR3 alone — parcels
   intersected with slope, LULC, settlement buffers and a minimum-area filter —
   is a handful of PostGIS operators, versus fetching every polygon into Python
   and looping.
2. **GiST spatial indexes.** Without them, "which parcels fall inside this
   catchment" degrades to a full scan the moment the data outgrows a village.
3. **`ST_Transform` is the anti-hard-coding mechanism.** The UTM zone is derived
   per village from its own centroid and applied in SQL; there is no project CRS
   constant anywhere.
4. **Referential integrity for the audit trail.** Recommendations reference
   villages and jobs, and G6 requires an append-only audit log. Foreign keys and
   `CHECK` constraints do this in one migration.
5. **TimescaleDB is the same database.** The daily rainfall series in P3 becomes
   a hypertable rather than a second data store.

## Alternatives rejected

- **MongoDB.** GeoJSON storage and `$geoWithin`/`$geoNear` are real, but the
  index is spherical-only, area and distance in projected metres are not
  available, and the multi-collection joins FR3 needs are application-side.
- **SQLite/SpatiaLite.** Fine for one village on a laptop; no concurrency story
  for the worker pool, and it undercuts the deployment story P6 is graded on.

## Consequences

A database server is required to run the system, which is why `make up` exists —
one command, or the installation-guide mark is lost. The `postgis/postgis` image
also installs the tiger geocoder and topology extensions, whose tables are
excluded from Alembic autogenerate in `migrations/env.py`.
