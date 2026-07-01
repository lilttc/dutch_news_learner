"""
Tests for embed_episodes.build_input_text.

Only touches the DB (a plain SubtitleSegment query), so a real in-memory
SQLite session is enough - no OpenAI calls happen here, unlike the actual
embedding step which is exercised via src/rag.py's mocked-client tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scripts.embed_episodes import build_input_text
from src.models import Base, Episode, SubtitleSegment


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    yield s
    s.close()


def _make_episode(session, **kwargs):
    defaults = {"video_id": "abc123", "title": "Test Episode", "description": "A test episode"}
    defaults.update(kwargs)
    ep = Episode(**defaults)
    session.add(ep)
    session.commit()
    return ep


def test_combines_title_description_and_transcript(session):
    ep = _make_episode(session)
    session.add_all(
        [
            SubtitleSegment(
                episode_id=ep.id,
                video_id=ep.video_id,
                text="Goedemiddag.",
                start_time=0.0,
                duration=1.0,
            ),
            SubtitleSegment(
                episode_id=ep.id,
                video_id=ep.video_id,
                text="Dit is het nieuws.",
                start_time=1.0,
                duration=1.0,
            ),
        ]
    )
    session.commit()

    text = build_input_text(session, ep)
    assert text == "Test Episode\nA test episode\nGoedemiddag. Dit is het nieuws."


def test_transcript_truncated_to_max_chars(session):
    ep = _make_episode(session, title="T", description="D")
    session.add(
        SubtitleSegment(
            episode_id=ep.id, video_id=ep.video_id, text="x" * 1000, start_time=0.0, duration=1.0
        )
    )
    session.commit()

    text = build_input_text(session, ep, max_transcript_chars=50)
    transcript_part = text.split("\n")[-1]
    assert len(transcript_part) == 50


def test_segments_joined_in_start_time_order_not_insertion_order(session):
    ep = _make_episode(session, title="T", description="D")
    session.add_all(
        [
            SubtitleSegment(
                episode_id=ep.id, video_id=ep.video_id, text="tweede", start_time=5.0, duration=1.0
            ),
            SubtitleSegment(
                episode_id=ep.id, video_id=ep.video_id, text="eerste", start_time=1.0, duration=1.0
            ),
        ]
    )
    session.commit()

    text = build_input_text(session, ep)
    assert text.endswith("eerste tweede")


def test_missing_description_skipped_not_blank_line(session):
    ep = _make_episode(session, title="T", description=None)
    text = build_input_text(session, ep)
    assert text == "T"
