"""FastAPI smoke tests - isolated SQLite, no external services."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_session_creates_token(client: TestClient) -> None:
    r = client.get("/api/session")
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert "user_id" in data
    assert len(data["token"]) == 36


def test_register_login_me(client: TestClient) -> None:
    r = client.post(
        "/api/auth/register",
        json={"email": "pytest-user@example.com", "password": "testpass12"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "pytest-user@example.com"
    token = body["access_token"]
    assert token

    r2 = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["email"] == "pytest-user@example.com"


def test_me_unauthorized(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_list_episodes_empty(client: TestClient) -> None:
    r = client.get("/api/episodes")
    assert r.status_code == 200
    assert r.json() == []


def test_episode_detail_not_found(client: TestClient) -> None:
    r = client.get("/api/episodes/99999")
    assert r.status_code == 404


def test_episode_detail_serializes_populated_episode(client: TestClient) -> None:
    """A populated episode must serialize through GET /api/episodes/{id}: if segment
    ordering, vocab nesting, or dictionary enrichment breaks, learners see a scrambled
    or empty episode page. Guards the selectinload/defer swap in commit 3e36447."""
    import json as _json

    from src.models import (
        Episode,
        EpisodeVocabulary,
        SubtitleSegment,
        VocabularyItem,
        get_engine,
        get_session,
    )

    engine = get_engine()
    session = get_session(engine)
    try:
        ep = Episode(
            video_id="pytest-detail-ep",
            title="Olie en water in het nieuws",
            description="Een testaflevering.",
            topics="olie|water",
            transcript_fetched=True,
            related_articles=_json.dumps(
                [
                    {
                        "topic": "olie",
                        "title": "Olieprijs stijgt",
                        "url": "https://example.com/olie",
                        "snippet": "De prijs van olie is gestegen.",
                    }
                ]
            ),
        )
        session.add(ep)
        session.flush()

        # Inserted out of start_time order - the endpoint must sort them.
        session.add_all(
            [
                SubtitleSegment(
                    episode_id=ep.id,
                    video_id=ep.video_id,
                    text="Dit is de tweede zin.",
                    translation_en="This is the second sentence.",
                    start_time=5.0,
                    duration=2.0,
                ),
                SubtitleSegment(
                    episode_id=ep.id,
                    video_id=ep.video_id,
                    text="Dit is de eerste zin.",
                    translation_en="This is the first sentence.",
                    start_time=1.0,
                    duration=2.0,
                ),
            ]
        )

        v_water = VocabularyItem(lemma="water", pos="NOUN")
        v_olie = VocabularyItem(lemma="olie", pos="NOUN", translation="crude oil")
        v_qa = VocabularyItem(
            lemma="pytestqawoord",
            pos="NOUN",
            translation="original translation",
            qa_translation="qa override translation",
            qa_checked=True,
        )
        session.add_all([v_water, v_olie, v_qa])
        session.flush()

        session.add_all(
            [
                EpisodeVocabulary(
                    episode_id=ep.id,
                    vocabulary_id=v_water.id,
                    occurrence_count=10,
                    example_sentence="Ze drinken water.",
                ),
                EpisodeVocabulary(
                    episode_id=ep.id,
                    vocabulary_id=v_olie.id,
                    occurrence_count=5,
                    example_sentence="De olie is duur.",
                ),
                EpisodeVocabulary(
                    episode_id=ep.id,
                    vocabulary_id=v_qa.id,
                    occurrence_count=1,
                    example_sentence="Een zin met pytestqawoord.",
                ),
            ]
        )
        session.commit()
        ep_id = ep.id
        qa_vocab_id = v_qa.id
    finally:
        session.close()

    r = client.get(f"/api/episodes/{ep_id}")
    assert r.status_code == 200
    body = r.json()

    # Episode fields (EpisodeDetailOut)
    assert body["id"] == ep_id
    assert body["video_id"] == "pytest-detail-ep"
    assert body["title"] == "Olie en water in het nieuws"
    assert body["description"] == "Een testaflevering."
    assert body["topics"] == "olie|water"

    # Segments (SegmentOut) - all present, sorted by start_time ascending
    segs = body["segments"]
    assert [s["start_time"] for s in segs] == [1.0, 5.0]
    assert segs[0]["text"] == "Dit is de eerste zin."
    assert segs[0]["translation_en"] == "This is the first sentence."
    assert segs[0]["duration"] == 2.0
    assert set(segs[0]) >= {"id", "text", "translation_en", "start_time", "duration"}

    # Vocabulary (VocabWordOut) - sorted by occurrence_count descending
    vocab = body["vocabulary"]
    assert [w["lemma"] for w in vocab] == ["water", "olie", "pytestqawoord"]
    by_lemma = {w["lemma"]: w for w in vocab}

    # "water" has no VocabularyItem.translation -> enrichment comes from the dictionary:
    # meaning_en is the English gloss, meaning falls back to the Dutch gloss.
    assert by_lemma["water"]["meaning_en"] == "water"
    assert isinstance(by_lemma["water"]["meaning"], str) and by_lemma["water"]["meaning"]
    assert by_lemma["water"]["occurrence_count"] == 10
    assert by_lemma["water"]["status"] == "new"

    # "olie" has VocabularyItem.translation set -> that wins for the NL/primary meaning,
    # dictionary fallback still supplies the English gloss.
    assert by_lemma["olie"]["meaning"] == "crude oil"
    assert by_lemma["olie"]["meaning_en"] == "oil"
    assert by_lemma["olie"]["example_sentence"] == "De olie is duur."
    assert set(by_lemma["olie"]) >= {
        "vocabulary_id",
        "lemma",
        "pos",
        "occurrence_count",
        "surface_forms",
        "example_sentence",
        "meaning",
        "meaning_en",
        "status",
    }

    # NOTE: locked decision 1 says the display layer must prefer qa_translation over
    # translation. This endpoint does NOT - it returns v.translation directly. The
    # code-reviewer flagged that as a separate pre-existing bug. This assertion
    # documents the CURRENT (wrong) behavior so the test doesn't imply correctness.
    assert by_lemma["pytestqawoord"]["vocabulary_id"] == qa_vocab_id
    assert by_lemma["pytestqawoord"]["meaning"] == "original translation"
    assert by_lemma["pytestqawoord"]["meaning"] != "qa override translation"

    # Related articles (ArticleOut)
    assert body["related_articles"] == [
        {
            "topic": "olie",
            "title": "Olieprijs stijgt",
            "url": "https://example.com/olie",
            "snippet": "De prijs van olie is gestegen.",
        }
    ]


def test_vocab_status_and_export(client: TestClient) -> None:
    from src.models import VocabularyItem, get_engine, get_session

    engine = get_engine()
    session = get_session(engine)
    try:
        v = VocabularyItem(lemma="pytestwoord", pos="NOUN")
        session.add(v)
        session.commit()
        session.refresh(v)
        vid = v.id
    finally:
        session.close()

    r = client.put(
        f"/api/vocabulary/{vid}/status",
        json={"status": "learning"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "learning"
    assert r.json()["lemma"] == "pytestwoord"

    r2 = client.get("/api/vocabulary/status")
    assert r2.status_code == 200
    rows = r2.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "learning"

    r3 = client.get("/api/vocabulary/export?format=json")
    assert r3.status_code == 200
    assert isinstance(r3.json(), list)
