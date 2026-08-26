"""FastAPI dependencies for authentication and role checks."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from app.core.security import AuthenticationError, AuthorizationError, Principal, verify
from app.domain.recommendation import role_allows


def current_principal(authorization: Annotated[str | None, Header()] = None) -> Principal:
    """Bearer token → principal; anonymous callers are viewers."""
    if not authorization:
        return Principal(username="anonymous", role="viewer")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        msg = "expected 'Authorization: Bearer <token>'"
        raise AuthenticationError(msg)
    return verify(token)


PrincipalDep = Annotated[Principal, Depends(current_principal)]


def require_role(role: str) -> object:
    """Dependency factory: ``403`` unless the caller's role covers ``role``."""

    def _check(principal: PrincipalDep) -> Principal:
        if not role_allows(principal.role, role):
            msg = f"this action requires the {role} role"
            raise AuthorizationError(msg, {"role": principal.role, "required": role})
        return principal

    return Depends(_check)
