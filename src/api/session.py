"""
User resolution for per-user vocabulary (Phase 6E + 6F).

Priority: Bearer token (registered user) > X-Session-Token (anonymous) > legacy (1).

If the client sends a session token (header or query), it must be a valid UUID and
the DB must succeed - we never silently map those requests onto shared legacy user_id=1.
"""

import logging
import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import AnonymousSession

from .auth import get_current_user_optional
from .deps import get_db

LEGACY_USER_ID = 1

_logger = logging.getLogger(__name__)


def get_or_create_session(db: Session, token: str) -> int:
    """
    Look up or create an anonymous session by token. Returns user_id (session id).

    Args:
        db: Database session.
        token: UUID string from localStorage (Next.js) or URL param (Streamlit).

    Returns:
        user_id: The session's id, used as user_id in UserVocabulary.
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


def get_user_id(
    request: Request,
    db: Session = Depends(get_db),
) -> int:
    """
    FastAPI dependency: resolve request to user_id.

    Priority: Bearer token (registered) > X-Session-Token (anonymous) > legacy (1).
    """
    # 1. Check for authenticated user (JWT Bearer token)
    user = get_current_user_optional(request, db)
    if user is not None:
        return user.id

    # 2. Fall back to anonymous session (X-Session-Token)
    token = request.headers.get("X-Session-Token") or request.query_params.get("token")
    if not token or not token.strip():
        return LEGACY_USER_ID

    token = token.strip()
    try:
        uuid.UUID(token)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid session token format",
        ) from None

    try:
        return get_or_create_session(db, token)
    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Anonymous session resolution failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to resolve session; please try again later.",
        ) from e


def create_session_token() -> str:
    """Generate a new UUID v4 token for anonymous sessions."""
    return str(uuid.uuid4())
