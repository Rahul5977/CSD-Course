"""Pure domain model: value objects, units, invariants, domain errors.

Framework-free by construction — no FastAPI, SQLAlchemy, rasterio, numpy-ndarray
plumbing or I/O. Every quantity carries its unit. ``mypy --strict`` runs over
this package specifically, and ``tests/test_layering.py`` fails the build if a
framework import appears here.
"""
