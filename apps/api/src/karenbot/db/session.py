from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from karenbot.config import get_settings

_engine = None
_session_factory: sessionmaker[Session] | None = None


def _normalized_database_url() -> str:
    """Accept bare postgres URLs from managed hosts (Railway/Heroku style).

    SQLAlchemy needs an explicit driver; hosts inject `postgresql://` (or the
    legacy `postgres://`). Normalize to psycopg so KARENBOT_DATABASE_URL can
    be set straight to the platform's DATABASE_URL reference.
    """
    url = get_settings().database_url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_normalized_database_url(), pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commits on success, rolls back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
