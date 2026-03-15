"""Shared dependencies for API routes."""

from collections.abc import Generator

from src.dictionary import get_lookup
from src.dictionary.lookup import DictionaryLookup
from src.models import get_engine, get_session


def get_db() -> Generator:
    """Yield a database session, closing it after the request."""
    engine = get_engine()
    session = get_session(engine)
    try:
        yield session
    finally:
        session.close()


def get_dictionary() -> DictionaryLookup:
    return get_lookup()
