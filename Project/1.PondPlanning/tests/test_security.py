"""JWT issuance/verification and role gating."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import AuthenticationError, User, issue_tokens, parse_users, verify


def test_tokens_round_trip_and_expire() -> None:
    user = User("officer", "x", "officer")
    tokens = issue_tokens(user)
    principal = verify(str(tokens["access_token"]))
    assert principal.username == "officer" and principal.role == "officer"
    with pytest.raises(AuthenticationError):
        verify(str(tokens["refresh_token"]))  # wrong type for an access check
    old = issue_tokens(user, now=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(AuthenticationError):
        verify(str(old["access_token"]))
    with pytest.raises(AuthenticationError):
        verify("not.a.token")


def test_users_are_parsed_from_settings() -> None:
    users = parse_users(get_settings().users)
    assert users["officer"].role == "officer" and users["viewer"].role == "viewer"


def test_login_refresh_and_me(client: TestClient) -> None:
    bad = client.post("/api/v1/auth/token", json={"username": "officer", "password": "wrong"})
    assert bad.status_code == 401 and bad.json()["code"] == "unauthenticated"
    ok = client.post("/api/v1/auth/token", json={"username": "officer", "password": "officer-demo"})
    assert ok.status_code == 200
    tokens = ok.json()
    assert tokens["role"] == "officer" and tokens["expires_in"] == 900
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.json() == {"username": "officer", "role": "officer"}
    assert client.get("/api/v1/auth/me").json()["role"] == "viewer"
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200 and refreshed.json()["role"] == "officer"
    garbage = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nope"})
    assert garbage.status_code == 401
