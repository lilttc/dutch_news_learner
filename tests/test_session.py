"""
Unit tests for src/api/session.py - pure utility functions.

get_or_create_session and get_user_id require DB/Request and are covered
by test_api_smoke.py at the endpoint level. Here we test the pure utilities.
"""

import uuid

from src.api.session import create_session_token


def test_create_session_token_is_valid_uuid() -> None:
    token = create_session_token()
    parsed = uuid.UUID(token)
    assert str(parsed) == token


def test_create_session_token_is_unique() -> None:
    tokens = {create_session_token() for _ in range(50)}
    assert len(tokens) == 50


def test_create_session_token_is_version_4() -> None:
    token = create_session_token()
    assert uuid.UUID(token).version == 4
