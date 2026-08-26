"""Upload hardening for the contour route: extension whitelist and size cap.

Request-level validation, not business logic: nothing here knows what a
contour is. The engine does its own strict parsing behind this gate (ADR 0012).
"""

from __future__ import annotations

import re

from fastapi import UploadFile

from app.domain.errors import UnsupportedInputError, ValidationError

ALLOWED_EXTENSIONS = (".kml", ".kmz")
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str | None) -> str:
    """Strip path components and unsafe characters; never empty."""
    base = (name or "upload.kml").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = _SAFE.sub("_", base).strip("._") or "upload.kml"
    return cleaned[:120]


def read_contour_upload(file: UploadFile, max_mb: int) -> tuple[str, bytes]:
    """Validate and read the upload. Returns ``(safe filename, bytes)``.

    Raises:
        UnsupportedInputError: Wrong extension.
        ValidationError: Empty, or over the configured size cap.
    """
    name = safe_filename(file.filename)
    if not name.lower().endswith(ALLOWED_EXTENSIONS):
        msg = "only .kml and .kmz contour maps are accepted"
        raise UnsupportedInputError(msg, {"filename": name, "allowed": list(ALLOWED_EXTENSIONS)})
    payload = file.file.read(max_mb * 1024 * 1024 + 1)
    if not payload:
        msg = "the uploaded file is empty"
        raise ValidationError(msg, {"filename": name})
    if len(payload) > max_mb * 1024 * 1024:
        msg = f"upload exceeds the {max_mb} MB limit"
        raise ValidationError(msg, {"filename": name, "max_mb": max_mb})
    return name, payload
