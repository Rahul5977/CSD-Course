"""JWT (RS256) issuance and verification, and role-based access control (P6).

Access tokens live 15 minutes, refresh tokens 7 days. RS256 rather than
HS256 so that a verifier (a second service, a reverse proxy) only ever
holds the public key. Keys come from PEM files named in settings; when
absent — a laptop, CI — an ephemeral pair is generated at start-up with a
warning, so ``make up`` never fails for want of a key and production cannot
silently run on a throw-away one.

Users are a small configured list (``POND_USERS``), because the assignment
has no identity provider; the point is the *gate*, not the directory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings, get_settings
from app.domain.errors import DomainError

logger = logging.getLogger(__name__)

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=7)
ALGORITHM = "RS256"


class AuthenticationError(DomainError):
    """Missing, expired or invalid credentials."""

    code = "unauthenticated"


class AuthorizationError(DomainError):
    """The caller is known but lacks the role."""

    code = "forbidden"


@dataclass(frozen=True, slots=True)
class User:
    """A configured user."""

    username: str
    password: str
    role: str


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is calling, from a verified token."""

    username: str
    role: str


@dataclass(frozen=True, slots=True)
class KeyPair:
    """PEM-encoded RSA keys."""

    private_pem: bytes
    public_pem: bytes
    ephemeral: bool


def _generate() -> KeyPair:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return KeyPair(private, public, ephemeral=True)


@lru_cache(maxsize=1)
def load_keys() -> KeyPair:
    """Keys from settings, else an ephemeral pair (logged)."""
    settings = get_settings()
    private_path = Path(settings.jwt_private_key_path) if settings.jwt_private_key_path else None
    public_path = Path(settings.jwt_public_key_path) if settings.jwt_public_key_path else None
    if private_path and public_path and private_path.is_file() and public_path.is_file():
        return KeyPair(private_path.read_bytes(), public_path.read_bytes(), ephemeral=False)
    logger.warning("no JWT key files configured; using an ephemeral RS256 key pair")
    return _generate()


def parse_users(spec: str) -> dict[str, User]:
    """``user:password:role,...`` → users."""
    users: dict[str, User] = {}
    for item in filter(None, (part.strip() for part in spec.split(","))):
        username, password, role = item.split(":", 2)
        users[username] = User(username, password, role)
    return users


def authenticate(settings: Settings, username: str, password: str) -> User:
    """Check a username/password against the configured list.

    Raises:
        AuthenticationError: On a wrong username or password.
    """
    user = parse_users(settings.users).get(username)
    if user is None or user.password != password:
        msg = "invalid username or password"
        raise AuthenticationError(msg)
    return user


def issue_tokens(user: User, now: datetime | None = None) -> dict[str, str | int]:
    """Access + refresh JWTs for a user."""
    now = now or datetime.now(UTC)
    keys = load_keys()
    base = {"sub": user.username, "role": user.role, "iat": int(now.timestamp())}
    access = jwt.encode(
        {**base, "typ": "access", "exp": int((now + ACCESS_TTL).timestamp())},
        keys.private_pem,
        algorithm=ALGORITHM,
    )
    refresh = jwt.encode(
        {**base, "typ": "refresh", "exp": int((now + REFRESH_TTL).timestamp())},
        keys.private_pem,
        algorithm=ALGORITHM,
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": int(ACCESS_TTL.total_seconds()),
    }


def verify(token: str, expected_type: str = "access") -> Principal:
    """Decode and validate a token.

    Raises:
        AuthenticationError: If the signature, expiry or type is wrong.
    """
    try:
        claims = jwt.decode(token, load_keys().public_pem, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        msg = f"invalid token: {exc}"
        raise AuthenticationError(msg) from exc
    if claims.get("typ") != expected_type:
        msg = f"expected a {expected_type} token"
        raise AuthenticationError(msg)
    return Principal(username=str(claims["sub"]), role=str(claims.get("role", "viewer")))
