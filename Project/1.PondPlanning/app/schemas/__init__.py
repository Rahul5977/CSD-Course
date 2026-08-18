"""Pydantic request/response models — the wire contract.

Separate from ``domain`` on purpose: the HTTP shape is allowed to change for
API-versioning reasons without perturbing the domain model, and vice versa.
"""
