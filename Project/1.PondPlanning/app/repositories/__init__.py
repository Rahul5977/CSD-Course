"""Persistence layer: SQLAlchemy models and repository classes.

Engines depend on repository *Protocols*, never on SQLAlchemy directly, so the
hydrology chain stays unit-testable without a database.
"""
