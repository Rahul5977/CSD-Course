"""Exception handlers — the single place that maps domain errors to HTTP.

Engines raise :class:`app.domain.errors.DomainError`; they never import FastAPI
and never choose a status code. This module is the only translation point, which
is what keeps the engines framework-free and the error catalogue authoritative:
one table here, one section in the API docs, no drift between them.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.backpressure import BackpressureError
from app.core.security import AuthenticationError, AuthorizationError
from app.domain.errors import (
    CRSError,
    DomainError,
    ElevationNotFoundError,
    GeometryError,
    JobFailedError,
    NotFoundError,
    NotImplementedYetError,
    UnsupportedInputError,
    UpstreamUnavailableError,
    ValidationError,
)
from app.domain.recommendation import IllegalTransitionError
from app.schemas.common import ProblemDetail

logger = logging.getLogger(__name__)

DOC_BASE = "https://github.com/Rahul5977/AI-BasedPondAnalysis/blob/main/docs/api/errors.md"

# The error catalogue. Adding a domain error without adding a row here makes it a
# 500, which the contract test in tests/test_errors.py catches.
STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_400_BAD_REQUEST,
    GeometryError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    CRSError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    UnsupportedInputError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ElevationNotFoundError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    JobFailedError: status.HTTP_409_CONFLICT,
    UpstreamUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
    NotImplementedYetError: status.HTTP_501_NOT_IMPLEMENTED,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    AuthorizationError: status.HTTP_403_FORBIDDEN,
    IllegalTransitionError: status.HTTP_409_CONFLICT,
    BackpressureError: status.HTTP_429_TOO_MANY_REQUESTS,
}


def status_for(error: DomainError) -> int:
    """Resolve the HTTP status for a domain error, honouring subclasses."""
    for cls in type(error).__mro__:
        if cls in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[cls]
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def problem(error: DomainError, request: Request) -> JSONResponse:
    """Render a domain error as an RFC 9457 problem document."""
    code = status_for(error)
    body = ProblemDetail(
        type=f"{DOC_BASE}#{error.code}",
        title=error.message,
        status=code,
        code=error.code,
        detail=error.detail,
        instance=request.url.path,
    )
    headers = (
        {"Retry-After": str(error.retry_after_s)} if isinstance(error, BackpressureError) else None
    )
    return JSONResponse(status_code=code, content=body.model_dump(mode="json"), headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers so every error leaves this API in one documented shape."""

    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        if status_for(exc) >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.exception("unmapped domain error", extra={"code": exc.code})
        return problem(exc, request)

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Reshape FastAPI's default 422 into the same problem document."""
        body = ProblemDetail(
            type=f"{DOC_BASE}#request_validation_error",
            title="The request body or parameters failed validation",
            status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="request_validation_error",
            detail={"errors": exc.errors()},
            instance=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=body.model_dump(mode="json"),
        )
