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
