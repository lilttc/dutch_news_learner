"""
Anonymous session handling (Phase 6E).

Resolves X-Session-Token to user_id for per-user vocabulary. When no token
is provided, returns 1 (legacy shared user). When a valid token is provided,
looks up or creates an AnonymousSession and uses its id as user_id.
"""

import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.models import AnonymousSession

from .deps import get_db

LEGACY_USER_ID = 1


def get_or_create_session(db: Session, token: str) -> int:
    """
    Look up or create an anonymous session by token. Returns user_id (session id).

    Args:
        db: Database session.
        token: UUID string from client (localStorage or URL param).

    Returns:
        user_id: The session's id, used as user_id in UserVocabulary.
    """
    session = db.query(AnonymousSession).filter_by(token=token).first()
    if session:
        return session.id

    new_session = AnonymousSession(token=token)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session.id


def get_user_id(
    request: Request,
    db: Session = Depends(get_db),
) -> int:
    """
    FastAPI dependency: resolve request to user_id.

    Reads X-Session-Token header or token query param. If missing or invalid,
    returns LEGACY_USER_ID (1). Otherwise lookup/create session, return its id.
    """
    token = (
        request.headers.get("X-Session-Token")
        or request.query_params.get("token")
    )
    if not token or not token.strip():
        return LEGACY_USER_ID

    token = token.strip()
    # Basic UUID format validation (36 chars, hex + hyphens)
    if len(token) != 36 or token.count("-") != 4:
        return LEGACY_USER_ID

    try:
        return get_or_create_session(db, token)
    except Exception:
        return LEGACY_USER_ID


def create_session_token() -> str:
    """Generate a new UUID v4 token for anonymous sessions."""
    return str(uuid.uuid4())
