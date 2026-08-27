"""
Anonymous-session resolution (Phase 6E), framework-free.

Each visitor without an account gets a UUID token (localStorage in Next.js, URL
param in Streamlit); the matching ``AnonymousSession`` row's id is used as
``user_id`` in ``UserVocabulary`` (the 2..999999 band - see the user_id
partitioning invariant in the models). ``user_id == LEGACY_USER_ID`` (1) is the
shared fallback for requests with no token.

This module has no FastAPI import so non-API surfaces (the Streamlit app) can
resolve sessions directly. The FastAPI request dependency ``get_user_id`` lives
in ``src.api.session``, which re-exports the names here.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import AnonymousSession

LEGACY_USER_ID = 1


def get_or_create_session(db: Session, token: str) -> int:
    """
    Look up or create an anonymous session by token. Returns the session id
    (used as ``user_id`` in ``UserVocabulary``).

    Concurrency-safe: on a duplicate-token ``IntegrityError`` from a racing
    insert, rolls back and re-reads the row that won.

    Args:
        db: Database session.
        token: UUID string from localStorage (Next.js) or URL param (Streamlit).

    Returns:
        The session's id, used directly as ``user_id``. Allocated by
        ``AnonymousSession`` autoincrement and stays in the 2–999999 anonymous
        band (locked decision 3: user_id space is partitioned by range).
    """
    session = db.query(AnonymousSession).filter_by(token=token).first()
    if session:
        return session.id

    new_session = AnonymousSession(token=token)
    db.add(new_session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        session = db.query(AnonymousSession).filter_by(token=token).first()
        if session:
            return session.id
        raise
    db.refresh(new_session)
    return new_session.id


def create_session_token() -> str:
    """Generate a new UUID v4 token for an anonymous session."""
    return str(uuid.uuid4())
