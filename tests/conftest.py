"""
Pytest setup: isolate DB and secrets before importing the FastAPI app.

``src.api.deps`` binds ``get_engine()`` at import time, so ``DATABASE_URL`` and
``SECRET_KEY`` must be set before ``from src.api.main import app``.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Temporary SQLite file (not :memory: - engine pool needs a shared file path).
_tmp_db = tempfile.NamedTemporaryFile(suffix=".pytest-dnl.db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["SECRET_KEY"] = "pytest-secret-key-at-least-32-characters"

from src.api.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as ac:
        yield ac


def pytest_sessionfinish(session, exitstatus: int) -> None:
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass
