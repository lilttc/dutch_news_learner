"""
Tests for src.rag.

Two things matter here: (1) semantic search must refuse to run on the SQLite
dev fallback rather than silently returning wrong results (regression guard
for that dialect check), and (2) answer_question's context/citation assembly,
verified with search_episodes and the OpenAI client mocked so no real
embedding call or Postgres connection is needed.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Episode, SubtitleSegment
from src.rag import (
    answer_question,
    episode_transcript,
    is_semantic_search_available,
    search_episodes,
)


@pytest.fixture
def sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    yield s
    s.close()


def test_semantic_search_unavailable_on_sqlite(sqlite_session):
    assert is_semantic_search_available(sqlite_session) is False


def test_search_episodes_raises_on_sqlite(sqlite_session):
    with pytest.raises(RuntimeError, match="Postgres"):
        search_episodes(sqlite_session, "some question")


def test_answer_question_raises_on_sqlite(sqlite_session):
    with pytest.raises(RuntimeError, match="Postgres"):
        answer_question(sqlite_session, "some question")


def test_episode_transcript_joins_segments_in_start_time_order(sqlite_session):
    ep = Episode(video_id="abc123", title="Test")
    sqlite_session.add(ep)
    sqlite_session.commit()
    sqlite_session.add_all(
        [
            SubtitleSegment(
                episode_id=ep.id, video_id=ep.video_id, text="tweede", start_time=5.0, duration=1.0
            ),
            SubtitleSegment(
                episode_id=ep.id, video_id=ep.video_id, text="eerste", start_time=1.0, duration=1.0
            ),
        ]
    )
    sqlite_session.commit()
    assert episode_transcript(sqlite_session, ep) == "eerste tweede"


def _make_mock_client(answer_text: str) -> MagicMock:
    message = SimpleNamespace(content=answer_text)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice])
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


def test_answer_question_cites_retrieved_episodes(sqlite_session):
    """With search_episodes mocked (bypassing the real Postgres/embedding path),
    the prompt sent to the model must include each retrieved episode's date and
    title, and the returned episodes must match what was retrieved."""
    ep1 = Episode(video_id="v1", title="Stikstof nieuws", published_at=datetime(2026, 6, 1))
    ep2 = Episode(video_id="v2", title="Weer nieuws", published_at=datetime(2026, 6, 2))
    sqlite_session.add_all([ep1, ep2])
    sqlite_session.commit()

    client = _make_mock_client("The government announced new rules. [2026-06-01]")

    with patch("src.rag.search_episodes", return_value=[ep1, ep2]):
        result = answer_question(sqlite_session, "What happened with stikstof?", client=client)

    assert result["answer"] == "The government announced new rules. [2026-06-01]"
    assert result["episodes"] == [ep1, ep2]

    prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "2026-06-01" in prompt
    assert "Stikstof nieuws" in prompt
    assert "2026-06-02" in prompt
    assert "Weer nieuws" in prompt


def test_answer_question_no_episodes_found_skips_llm_call(sqlite_session):
    client = _make_mock_client("should not be used")
    with patch("src.rag.search_episodes", return_value=[]):
        result = answer_question(sqlite_session, "anything", client=client)
    assert result == {"answer": "No matching episodes found.", "episodes": []}
    client.chat.completions.create.assert_not_called()
