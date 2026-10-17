"""
Unit tests for the Postgres connect retry in src/models/db.py.

A transient connect failure (Neon waking from suspend drops the TLS handshake)
must be retried with backoff rather than failing the pipeline step. No real
database is needed: the DBAPI ``connect`` is a fake.
"""

import pytest
from src.models.db import _CONNECT_RETRY_DELAYS, _connect_with_retry, get_engine


class FakeOperationalError(Exception):
    """Stands in for psycopg2.OperationalError."""


def _flaky_connect(failures: int):
    """Return a fake connect that raises FakeOperationalError ``failures`` times, then succeeds."""
    calls = []

    def connect(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) <= failures:
            raise FakeOperationalError("SSL SYSCALL error: EOF detected")
        return "conn"

    return connect, calls


def test_succeeds_first_try_without_sleeping() -> None:
    connect, calls = _flaky_connect(0)
    sleeps = []
    conn = _connect_with_retry(connect, ("dsn",), {"x": 1}, FakeOperationalError, sleeps.append)
    assert conn == "conn"
    assert calls == [(("dsn",), {"x": 1})]
    assert sleeps == []


def test_retries_transient_failures_with_backoff() -> None:
    connect, calls = _flaky_connect(2)
    sleeps = []
    conn = _connect_with_retry(connect, (), {}, FakeOperationalError, sleeps.append)
    assert conn == "conn"
    assert len(calls) == 3
    assert sleeps == list(_CONNECT_RETRY_DELAYS[:2])


def test_raises_last_error_after_all_attempts() -> None:
    connect, calls = _flaky_connect(99)
    sleeps = []
    with pytest.raises(FakeOperationalError):
        _connect_with_retry(connect, (), {}, FakeOperationalError, sleeps.append)
    assert len(calls) == len(_CONNECT_RETRY_DELAYS) + 1
    assert sleeps == list(_CONNECT_RETRY_DELAYS)


def test_non_transient_error_is_not_retried() -> None:
    sleeps = []

    def connect(*args, **kwargs):
        raise ValueError("bad dsn")

    with pytest.raises(ValueError):
        _connect_with_retry(connect, (), {}, FakeOperationalError, sleeps.append)
    assert sleeps == []


def test_postgres_engine_registers_retrying_connect() -> None:
    eng = get_engine("postgresql://user:pw@localhost:1/db")
    # do_connect is a dialect-level event, so listeners live on the dialect.
    assert len(eng.dialect.dispatch.do_connect) == 1


def test_sqlite_engine_has_no_retry_hook() -> None:
    eng = get_engine("sqlite:///:memory:")
    assert len(eng.dialect.dispatch.do_connect) == 0
