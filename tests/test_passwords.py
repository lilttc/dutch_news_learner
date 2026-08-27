"""
Unit tests for src/passwords.py (framework-free PBKDF2 password hashing).

``tests/test_auth.py`` exercises these via the ``src.api.auth`` re-export; this
module tests them at their real home so coverage does not depend on the API
layer importing. What would be wrong for a user: a broken hash/verify here means
nobody can register or log in to the Streamlit app.
"""

from src.passwords import hash_password, verify_password


def test_hash_is_not_plaintext() -> None:
    """A stored hash that equals the password would leak every credential on a DB dump."""
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"
    assert "hunter2" not in hashed


def test_verify_accepts_correct_password() -> None:
    """A registered user must be able to log in with their real password."""
    assert verify_password("correct horse battery staple", hash_password("correct horse battery staple"))


def test_verify_rejects_wrong_password_without_raising() -> None:
    """A wrong password must return False, never raise (which would 500 the login form)."""
    assert verify_password("wrong", hash_password("right")) is False


def test_hash_uses_pbkdf2_sha256_format() -> None:
    """Locked auth choice: PBKDF2-SHA256 (Werkzeug format), not bcrypt/passlib."""
    assert hash_password("x").startswith("pbkdf2:sha256")


def test_hash_is_salted_so_two_hashes_differ() -> None:
    """Unsalted hashes let an attacker precompute rainbow tables against the user table."""
    assert hash_password("samepass") != hash_password("samepass")


def test_verify_returns_false_on_malformed_hash() -> None:
    """A corrupt/foreign hash string must fail closed, not crash the caller."""
    assert verify_password("anything", "not-a-real-hash") is False
