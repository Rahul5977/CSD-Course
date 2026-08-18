"""Database engine and session factory.

Synchronous SQLAlchemy 2.0 on psycopg3, deliberately. The heavy work in this
system is terrain raster processing, which runs in a Celery worker rather than
in the request path, so the async-driver complexity would buy nothing while
adding a class of bug (blocking calls inside the event loop) that is easy to
introduce and hard to see. FastAPI runs sync dependencies in a threadpool.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,  # survives postgres restarts during development
    echo=_settings.debug,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Yield a request-scoped session, rolling back on error.

    FastAPI dependency. Commits are the caller's responsibility so that a route
    handling several repository calls still gets one transaction.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
