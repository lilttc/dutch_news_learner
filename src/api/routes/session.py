"""Anonymous session endpoint (Phase 6E)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db
from ..session import create_session_token, get_or_create_session

router = APIRouter(tags=["session"])


class SessionOut(BaseModel):
    """Session response: user_id and token for client to store."""

    user_id: int
    token: str


@router.get("/session", response_model=SessionOut)
def get_or_create_session_endpoint(
    token: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Get or create an anonymous session.

    - With token: look up existing session or create one. Returns user_id + token.
    - Without token: create new session with generated token. Returns user_id + token.

    Client should store the token in localStorage and send X-Session-Token
    header on subsequent requests.
    """
    if not token or not token.strip():
        token = create_session_token()

    token = token.strip()
    # Validate UUID format
    if len(token) != 36 or token.count("-") != 4:
        token = create_session_token()

    user_id = get_or_create_session(db, token)
    return SessionOut(user_id=user_id, token=token)
