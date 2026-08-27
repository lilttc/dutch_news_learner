"""
Password hashing for email auth (Phase 6F).

Framework-free: PBKDF2-SHA256 via Werkzeug only, no FastAPI import. Surfaces
that are not the API (the Streamlit app's login/register forms) hash and verify
through this module so they don't pull the whole FastAPI/Pydantic stack into
their process. ``src.api.auth`` re-exports these for the API layer.
"""

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    """
    Hash a password with PBKDF2-SHA256 (Werkzeug format).

    PBKDF2 is used rather than bcrypt to avoid the bcrypt/passlib import
    conflicts some environments hit when ``import bcrypt`` resolves incorrectly.
    """
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a Werkzeug PBKDF2-SHA256 hash."""
    return check_password_hash(hashed, plain)
