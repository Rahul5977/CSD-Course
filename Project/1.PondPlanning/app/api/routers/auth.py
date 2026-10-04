"""Token issuance (P6)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.auth import PrincipalDep
from app.api.deps import SettingsDep
from app.core.security import User, authenticate, issue_tokens, parse_users, verify

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    """Username/password grant."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Exchange a refresh token for a new pair."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Bearer tokens."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    role: str


@router.post("/token", response_model=TokenResponse, summary="Log in")
def token(payload: TokenRequest, settings: SettingsDep) -> TokenResponse:
    """RS256 access (15 min) + refresh (7 d) tokens for a configured user."""
    user = authenticate(settings, payload.username, payload.password)
    return TokenResponse(**issue_tokens(user), role=user.role)  # type: ignore[arg-type]


@router.post("/refresh", response_model=TokenResponse, summary="Refresh tokens")
def refresh(payload: RefreshRequest, settings: SettingsDep) -> TokenResponse:
    """A valid refresh token yields a new pair."""
    principal = verify(payload.refresh_token, expected_type="refresh")
    user = parse_users(settings.users).get(principal.username) or User(
        principal.username, "", principal.role
    )
    return TokenResponse(**issue_tokens(user), role=user.role)  # type: ignore[arg-type]


@router.get("/me", summary="Who am I")
def me(principal: PrincipalDep) -> dict[str, str]:
    """The caller's username and role (viewer when anonymous)."""
    return {"username": principal.username, "role": principal.role}
