"""Email auth endpoints (Phase 6F)."""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models import User

from ..auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..deps import get_db
from ..ratelimit import limiter

router = APIRouter(tags=["auth"])

# Email validation: basic format
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
MIN_PASSWORD_LEN = 8


class RegisterIn(BaseModel):
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class AuthOut(BaseModel):
    user_id: int
    email: str
    access_token: str


class MeOut(BaseModel):
    user_id: int
    email: str


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LEN} characters",
        )


def _validate_email(email: str) -> None:
    if not email or not email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if not EMAIL_RE.match(email.strip().lower()):
        raise HTTPException(status_code=400, detail="Invalid email format")


@router.post("/auth/register", response_model=AuthOut)
@limiter.limit("10/minute")
def register(
    request: Request,
    body: RegisterIn,
    db: Session = Depends(get_db),
):
    """
    Create a new account. Returns user_id, email, and access_token.
    Client should store the token and send it as Authorization: Bearer <token>.
    """
    _validate_email(body.email)
    _validate_password(body.password)

    email = body.email.strip().lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return AuthOut(user_id=user.id, email=user.email, access_token=token)


@router.post("/auth/login", response_model=AuthOut)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: LoginIn,
    db: Session = Depends(get_db),
):
    """
    Log in with email and password. Returns user_id, email, and access_token.
    """
    _validate_email(body.email)

    email = body.email.strip().lower()
    user = db.query(User).filter_by(email=email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.email)
    return AuthOut(user_id=user.id, email=user.email, access_token=token)


@router.get("/auth/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    """Return the current authenticated user. Requires Bearer token."""
    return MeOut(user_id=user.id, email=user.email)
