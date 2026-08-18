import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_is_built_from_parts() -> None:
    settings = Settings(
        postgres_user="u",
        postgres_password="p",
        postgres_host="h",
        postgres_port=1234,
        postgres_db="d",
    )

    assert settings.database_url == "postgresql+psycopg://u:p@h:1234/d"


def test_redis_url_is_built_from_parts() -> None:
    settings = Settings(redis_host="cache", redis_port=6380)

    assert settings.redis_url == "redis://cache:6380/0"


def test_settings_are_frozen() -> None:
    """Configuration is read once at startup; nothing mutates it afterwards."""
    settings = Settings()

    with pytest.raises(ValidationError):
        settings.env = "production"
