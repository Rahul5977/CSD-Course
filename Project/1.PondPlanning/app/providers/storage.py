"""Object storage port and its two adapters.

``MinioObjectStore`` is the deployment (S3-compatible, and what TiTiler reads
from). ``LocalObjectStore`` writes the same keys under a directory, so the
test suite and a laptop without Docker exercise the identical code path.
The choice is made once, from settings, in :func:`build_object_store`.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Protocol

from app.core.config import Settings


class ObjectStore(Protocol):
    """Put and get bytes by key; produce the URL a tile server can open."""

    def put(self, key: str, payload: bytes, content_type: str = "application/octet-stream") -> None:
        """Store bytes under ``key``, replacing any existing object."""
        ...

    def get(self, key: str) -> bytes:
        """Return the bytes stored under ``key``."""
        ...

    def exists(self, key: str) -> bool:
        """True when ``key`` is present."""
        ...

    def url(self, key: str) -> str:
        """A URL TiTiler (GDAL) can open — ``s3://`` or a file path."""
        ...


class LocalObjectStore:
    """Filesystem-backed store for tests and Docker-less development."""

    def __init__(self, root: Path) -> None:
        """Create ``root`` on demand."""
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents:
            msg = "object key escapes the store root"
            raise ValueError(msg)
        return path

    def put(self, key: str, payload: bytes, content_type: str = "application/octet-stream") -> None:
        """Write the bytes, creating parent directories."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def get(self, key: str) -> bytes:
        """Read the bytes."""
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        """Whether the file is present."""
        return self._path(key).is_file()

    def url(self, key: str) -> str:
        """Absolute file path."""
        return str(self._path(key))


class MinioObjectStore:
    """S3-compatible store; the bucket is created on first use."""

    def __init__(
        self, endpoint: str, access_key: str, secret_key: str, bucket: str, *, secure: bool
    ) -> None:
        """Connect lazily — the client opens no socket until the first call."""
        from minio import Minio

        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket
        self._ensured = False

    def _ensure_bucket(self) -> None:
        if not self._ensured:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
            self._ensured = True

    def put(self, key: str, payload: bytes, content_type: str = "application/octet-stream") -> None:
        """Upload the bytes."""
        self._ensure_bucket()
        self._client.put_object(
            self._bucket, key, io.BytesIO(payload), len(payload), content_type=content_type
        )

    def get(self, key: str) -> bytes:
        """Download the bytes."""
        response = self._client.get_object(self._bucket, key)
        try:
            return bytes(response.read())
        finally:
            response.close()
            response.release_conn()

    def exists(self, key: str) -> bool:
        """Whether the object is present."""
        from minio.error import S3Error

        try:
            self._client.stat_object(self._bucket, key)
        except S3Error:
            return False
        return True

    def url(self, key: str) -> str:
        """``s3://bucket/key`` — what TiTiler is configured to resolve."""
        return f"s3://{self._bucket}/{key}"


def build_object_store(settings: Settings) -> ObjectStore:
    """Factory: the adapter named in settings."""
    if settings.object_store == "minio":
        return MinioObjectStore(
            settings.minio_endpoint,
            settings.minio_access_key,
            settings.minio_secret_key,
            settings.minio_bucket,
            secure=settings.minio_secure,
        )
    return LocalObjectStore(Path(settings.local_store_dir))
