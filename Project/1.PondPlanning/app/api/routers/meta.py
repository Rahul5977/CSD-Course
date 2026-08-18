"""Machine-readable metadata about the API itself.

Two routes that cost almost nothing and answer questions an evaluator, a client
and the report all ask: what does this system actually implement right now, and
what can go wrong when I call it?
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import STATUS_BY_ERROR
from app.providers.fixtures import available

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/errors", summary="Error catalogue")
def error_catalogue() -> dict[str, list[dict[str, object]]]:
    """Every domain error this API can return, with its stable code and status.

    Generated from the handler table rather than written by hand, so the
    documentation cannot drift from the behaviour.
    """
    return {
        "errors": sorted(
            (
                {
                    "code": error.code,
                    "status": status,
                    "exception": error.__name__,
                    "description": (error.__doc__ or "").strip().split("\n")[0],
                }
                for error, status in STATUS_BY_ERROR.items()
            ),
            key=lambda row: str(row["code"]),
        )
    }


@router.get("/implementation-status", summary="What is real and what is a fixture")
def implementation_status() -> dict[str, object]:
    """Report which parts of the contract are backed by engines.

    Exists so "not built yet" is a documented state rather than something a
    caller has to infer. Every fixture-backed response also carries the
    ``X-Fixture-Data: true`` header and a ``fixture_data`` warning.
    """
    return {
        "phase": "P0 — Foundations & Contract",
        "engines_implemented": [],
        "fixture_backed": available(),
        "real": ["/health", "/ready", "/api/v1/meta/errors", "/api/v1/meta/implementation-status"],
        "note": (
            "Fixture routes exist so the frontend can be built against the final contract "
            "while the engines are written. Every fixture response sets X-Fixture-Data: true."
        ),
    }
