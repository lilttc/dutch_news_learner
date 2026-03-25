"""
FastAPI application for Dutch News Learner.

Provides REST endpoints for the Next.js frontend:
- Episodes list and detail
- Vocabulary with dictionary lookups
- User vocabulary status (known/learning/new)
- Related reading articles

Run with: uvicorn src.api.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

load_dotenv()

from src.models import _migrate_schema, get_engine

from .routes import auth, episodes, session, vocabulary

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify DB connectivity, then apply idempotent schema patches.

    Long-term, heavy DDL should move to Alembic and run in deploy — this startup
    path stays for compatibility until that migration exists.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        _logger.exception("Database unreachable during API startup (before schema migration)")
        raise
    _migrate_schema(engine)
    yield


app = FastAPI(
    title="Dutch News Learner API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(episodes.router, prefix="/api")
app.include_router(vocabulary.router, prefix="/api")
app.include_router(session.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
