"""
Unit tests for src/user_sessions.py (framework-free anonymous-session resolution).

``create_session_token`` is covered by ``tests/test_session.py`` via the
``src.api.session`` re-export. ``get_or_create_session`` had no direct unit test;
this module adds one.

What would be wrong for a user: if ``get_or_create_session`` returned a wrong or
colliding id, one visitor's known/learning vocabulary status would leak into
another's, or an id below 2 would collide with the shared ``__legacy__`` user
(locked decision 3: the user_id space is partitioned by range).
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.models import AnonymousSession, Base
from src.user_sessions import get_or_create_session


@pytest.fixture
def sqlite_session():
    """In-memory DB with the id=1 ``__legacy__`` sentinel row that production
    seeds via ``_migrate_schema()`` — so autoincremented session ids start at 2."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    s.execute(
        text(
            "INSERT INTO anonymous_sessions (id, token, created_at) "
            "VALUES (1, '__legacy__', datetime('now'))"
        )
    )
    s.commit()
    yield s
    s.close()


def test_creates_row_and_returns_its_id(sqlite_session) -> None:
    """A first-time visitor's token must produce a persisted session row."""
    new_id = get_or_create_session(sqlite_session, "tok-abc")
    row = sqlite_session.query(AnonymousSession).filter_by(token="tok-abc").one()
    assert row.id == new_id


def test_second_call_with_same_token_returns_same_id(sqlite_session) -> None:
    """A returning visitor must map to the same session id, not a fresh one —
    otherwise their saved vocab status vanishes on every page load."""
    first = get_or_create_session(sqlite_session, "tok-repeat")
    second = get_or_create_session(sqlite_session, "tok-repeat")
    assert first == second
    assert sqlite_session.query(AnonymousSession).filter_by(token="tok-repeat").count() == 1


def test_allocated_id_stays_in_anonymous_band(sqlite_session) -> None:
    """Locked decision 3: anonymous session ids are 2..999999; id 1 is the
    shared ``__legacy__`` sentinel and must never be handed out."""
    new_id = get_or_create_session(sqlite_session, "tok-band")
    assert 2 <= new_id < 1_000_000


def test_distinct_tokens_get_distinct_ids(sqlite_session) -> None:
    """Two different visitors must not collide onto one id."""
    a = get_or_create_session(sqlite_session, "tok-a")
    b = get_or_create_session(sqlite_session, "tok-b")
    assert a != b


def test_race_on_duplicate_insert_rolls_back_and_rereads_winner() -> None:
    """Concurrency guarantee: if a racing request inserts the same token first,
    the losing call must roll back and return the winner's id, not raise —
    otherwise a double-clicked first visit 500s."""
    db = MagicMock()
    winner = AnonymousSession(token="tok-race")
    winner.id = 42
    # First lookup (our stale snapshot) misses; post-rollback re-read hits.
    db.query.return_value.filter_by.return_value.first.side_effect = [None, winner]
    db.commit.side_effect = IntegrityError("duplicate token", None, Exception())

    result = get_or_create_session(db, "tok-race")

    assert result == 42
    db.rollback.assert_called_once()


def test_integrity_error_with_no_winner_row_propagates() -> None:
    """If the insert fails for a reason other than a real race (no row appears
    on re-read), the error must surface, not be swallowed into a bogus id."""
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.side_effect = [None, None]
    db.commit.side_effect = IntegrityError("some constraint", None, Exception())

    with pytest.raises(IntegrityError):
        get_or_create_session(db, "tok-broken")
