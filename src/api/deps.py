"""Shared dependencies for API routes."""

from collections.abc import Generator

from sqlalchemy.orm import sessionmaker

from src.dictionary import get_lookup
from src.dictionary.lookup import DictionaryLookup
from src.models import get_engine

_engine = get_engine()
_SessionLocal = sessionmaker(bind=_engine)


def get_db() -> Generator:
    """Yield a database session, closing it after the request."""
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_dictionary() -> DictionaryLookup:
    return get_lookup()
