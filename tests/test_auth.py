"""
Unit tests for src/api/auth.py.

Covers: password hashing, JWT round-trip, token expiry, invalid token handling,
and get_secret_key() fallback behaviour.

Note: conftest.py sets SECRET_KEY before the app is imported, so
create_access_token / decode_token work against that test key.
"""

import os
from datetime import timedelta
from unittest.mock import patch

import pytest

import src.api.auth as auth_module
from src.api.auth import (
    create_access_token,
    decode_token,
    get_secret_key,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_hash_and_verify_password() -> None:
    hashed = hash_password("mysecretpassword")
    assert verify_password("mysecretpassword", hashed) is True


def test_verify_wrong_password_returns_false() -> None:
    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_hash_is_not_plaintext() -> None:
    hashed = hash_password("mypassword")
    assert hashed != "mypassword"
    assert len(hashed) > 20


# ---------------------------------------------------------------------------
# JWT round-trip
# ---------------------------------------------------------------------------

def test_create_and_decode_token() -> None:
    token = create_access_token(user_id=42, email="test@example.com")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["email"] == "test@example.com"


def test_decode_invalid_token_returns_none() -> None:
    assert decode_token("this.is.not.a.valid.jwt") is None


def test_decode_garbage_returns_none() -> None:
    assert decode_token("notatoken") is None


def test_decode_tampered_token_returns_none() -> None:
    token = create_access_token(user_id=1, email="a@b.com")
    tampered = token[:-5] + "XXXXX"
    assert decode_token(tampered) is None


def test_token_contains_expiry() -> None:
    token = create_access_token(user_id=1, email="a@b.com")
    payload = decode_token(token)
    assert payload is not None
    assert "exp" in payload


# ---------------------------------------------------------------------------
# get_secret_key fallback behaviour
# ---------------------------------------------------------------------------

def test_get_secret_key_uses_env_var() -> None:
    with patch.dict(os.environ, {"SECRET_KEY": "my-test-secret-key-long-enough"}):
        with patch.object(auth_module, "_secret_key_cache", None):
            key = get_secret_key()
    assert key == "my-test-secret-key-long-enough"


def test_get_secret_key_dev_flag_fallback() -> None:
    env = {"SECRET_KEY": "", "ALLOW_INSECURE_DEV_JWT": "1"}
    with patch.dict(os.environ, env, clear=False):
        with patch.object(auth_module, "_secret_key_cache", None):
            key = get_secret_key()
    assert "insecure" in key.lower()


def test_get_secret_key_raises_without_config() -> None:
    env = {"SECRET_KEY": "", "ALLOW_INSECURE_DEV_JWT": "0"}
    with patch.dict(os.environ, env, clear=False):
        with patch.object(auth_module, "_secret_key_cache", None):
            with pytest.raises(RuntimeError, match="SECRET_KEY"):
                get_secret_key()
