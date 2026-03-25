"""
Email auth (Phase 6F): JWT tokens, password hashing, user resolution.

Priority for user_id: Bearer token (registered) > X-Session-Token (anonymous) > legacy (1).
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from src.models import User

from .deps import get_db

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

_secret_key_cache: str | None = None


def get_secret_key() -> str:
    """
    Return the JWT signing secret.

    * Production / staging: set ``SECRET_KEY`` (long random string, never commit it).
    * Local API only: you may set ``ALLOW_INSECURE_DEV_JWT=1`` to use a fixed
      dev-only key — **never** enable that in production (anyone could forge tokens).
    """
    global _secret_key_cache
    if _secret_key_cache is not None:
        return _secret_key_cache

    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        _secret_key_cache = key
        return _secret_key_cache

    flag = os.environ.get("ALLOW_INSECURE_DEV_JWT", "").lower()
    if flag in ("1", "true", "yes"):
        _secret_key_cache = "insecure-dev-only-do-not-use-in-production"
        return _secret_key_cache

    raise RuntimeError(
        "SECRET_KEY is required for JWT auth. Set SECRET_KEY in the environment, "
        "or for local development only set ALLOW_INSECURE_DEV_JWT=1 (never in production). "
        "See .env.example."
    )


def ensure_jwt_configured() -> None:
    """Fail fast at API startup if JWT signing is misconfigured."""
    get_secret_key()


def hash_password(password: str) -> str:
    """
    Hash password with PBKDF2-SHA256 (Werkzeug). Avoids bcrypt/passlib conflicts
    some environments have when `import bcrypt` resolves incorrectly.
    """
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify PBKDF2-SHA256 hash (Werkzeug format)."""
    return check_password_hash(hashed, plain)


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """
    Return the authenticated User if Bearer token is valid, else None.
    Does not raise — use get_current_user for protected routes.
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user_id_str = payload.get("sub")
    if not user_id_str:
        return None
    try:
        user_id = int(user_id_str)
    except ValueError:
        return None
    user = db.query(User).filter_by(id=user_id).first()
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Require authentication. Raises 401 if no valid Bearer token.
    """
    user = get_current_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
