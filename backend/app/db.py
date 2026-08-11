"""SQLAlchemy engine, session factory, and declarative base.

One engine per process, created from `Settings.database_url`. Sessions are
created per-request via the `get_db` FastAPI dependency and always closed
afterwards.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session, closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
