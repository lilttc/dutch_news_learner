"""
FastAPI request -> user_id resolution for per-user vocabulary (Phase 6E + 6F).

Priority: Bearer token (registered user) > X-Session-Token (anonymous) > legacy (1).

If the client sends a session token (header or query), it must be a valid UUID and
the DB must succeed - we never silently map those requests onto shared legacy user_id=1.

The framework-free session helpers (``get_or_create_session``,
``create_session_token``, ``LEGACY_USER_ID``) live in ``src.user_sessions`` and are
re-exported here.
"""

import logging
import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

# get_or_create_session / create_session_token / LEGACY_USER_ID are framework-free
# and live in src.user_sessions; re-exported here so API callers keep one import.
from src.user_sessions import LEGACY_USER_ID, create_session_token, get_or_create_session

from .auth import get_current_user_optional
from .deps import get_db

__all__ = [
    "LEGACY_USER_ID",
    "create_session_token",
    "get_or_create_session",
    "get_user_id",
]

_logger = logging.getLogger(__name__)


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
