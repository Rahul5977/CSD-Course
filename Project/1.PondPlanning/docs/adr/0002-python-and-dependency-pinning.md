# ADR 0002 — Python 3.12, uv, and a committed lockfile

**Status:** Accepted · 2026-08-18 · Phase P0

## Context

The development machine runs CPython 3.14. The geospatial stack this project
commits to — rasterio, pysheds, richdem, and numba in particular — lags the
newest CPython by one or two releases, because numba gates on the specific
bytecode it can compile. Discovering that in P2, mid-way through the catchment
engine, would cost a day of dependency archaeology at the worst possible moment.

Separately, G7 requires a fresh clone on a *different machine* to come up with
`make up`. That is not achievable with unpinned dependencies.

## Decision

- `requires-python = ">=3.12,<3.13"`. 3.12 has wheels for the entire P2/P3
  dependency set today.
- **uv** for dependency management, with `uv.lock` committed.
- The Docker image is built `FROM python:3.12-slim` and installs with
  `uv sync --frozen`, so the container and the laptop resolve identically.

## Alternatives rejected

- **Track the newest CPython.** Zero benefit for this workload and a guaranteed
  wheel problem at the exact moment the terrain engine lands.
- **`pip` + `requirements.txt`.** Works, but a hand-maintained requirements file
  is not a lockfile: it pins direct dependencies and lets transitive ones drift,
  which is precisely the failure mode "works on my machine" describes.
- **Conda/mamba,** the traditional answer for GDAL-adjacent stacks. Would have
  been defensible; rejected because manylinux wheels for rasterio and pysheds
  have been reliable for several releases, and a conda environment inside Docker
  roughly triples image size for no gain here.

## Consequences

`uv.lock` must be regenerated and committed with every dependency change, and CI
runs `uv sync --frozen` so that a stale lockfile fails the build rather than
silently resolving something different.
